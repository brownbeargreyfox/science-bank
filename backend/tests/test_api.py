import json

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from tests.conftest import TEACHER

PUBLIC = {"/healthz", "/readyz", "/api/auth/login", "/api/auth/logout", "/api/{path:path}"}


# ---- importer --------------------------------------------------------------------------------


def test_import_counts_and_idempotency(db):
    from app.core.config import get_settings
    from app.models import Bundle, BundleStandard, Course, Standard
    from app.standards.importer import import_standards

    assert db.scalar(select(func.count()).select_from(Standard)) == 38
    assert db.scalar(select(func.count()).select_from(Bundle)) == 15
    before = sorted(db.execute(select(Standard.id, Standard.content_sha256)).all())
    report = import_standards(db, get_settings().standards_dir)
    db.commit()
    assert report.created == {} and report.updated == {}
    assert report.unchanged == {"source_documents": 6, "courses": 3, "standards": 38, "bundles": 15}
    assert sorted(db.execute(select(Standard.id, Standard.content_sha256)).all()) == before
    # PE codes shared by Biology 1 and 2 are distinct rows with their own boundaries
    rows = db.execute(
        select(Course.slug, Standard.state_assessment_boundary).join(Course).where(Standard.code == "B-LS3-3")
    ).all()
    assert {r.slug for r in rows} == {"biology-1", "biology-2"}
    assert len({r.state_assessment_boundary for r in rows}) == 2
    # bundle alignments resolve inside their own course
    mismatched = db.scalar(
        select(func.count())
        .select_from(BundleStandard)
        .join(Bundle)
        .join(Standard, Standard.id == BundleStandard.standard_id)
        .where(Standard.course_id != Bundle.course_id)
    )
    assert mismatched == 0


# ---- auth ------------------------------------------------------------------------------------


def test_every_non_public_route_requires_auth(anon):
    from app.main import app

    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC or not route.path.startswith("/api"):
            continue
        path = route.path
        for name in route.param_convertors:
            path = path.replace("{" + name + "}", "1")
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = anon.request(method, path, json={})
            assert r.status_code == 401, f"{method} {route.path} -> {r.status_code}"
            checked += 1
    assert checked > 20


def test_login_logout_and_throttle(anon):
    assert anon.post("/api/auth/login", json={**TEACHER, "password": "wrong"}).status_code == 401
    assert anon.post("/api/auth/login", json={"username": "nobody", "password": "x"}).status_code == 401
    r = anon.post("/api/auth/login", json=TEACHER)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert anon.get("/api/auth/me").json() == {"username": "nina"}
    anon.post("/api/auth/logout")
    assert anon.get("/api/auth/me").status_code == 401
    for _ in range(8):
        anon.post("/api/auth/login", json={**TEACHER, "password": "wrong"})
    assert anon.post("/api/auth/login", json=TEACHER).status_code == 429


def test_registration_allows_multiple_teacher_accounts(anon):
    alex = {"username": "alex", "password": "another correct horse"}
    status = anon.get("/api/auth/registration-status")
    assert status.status_code == 200 and status.json() == {"registration_open": True}
    created = anon.post("/api/auth/register", json=alex)
    assert created.status_code == 201 and created.json() == {"username": "alex"}
    assert anon.post("/api/auth/register", json=alex).status_code == 409
    anon.post("/api/auth/logout")
    assert anon.post("/api/auth/login", json=alex).status_code == 200


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json() == {"detail": "Not found"}


# ---- standards -------------------------------------------------------------------------------


def _std(client, course_slug, code):
    return next(s for s in client.get("/api/standards").json() if s["course_slug"] == course_slug and s["code"] == code)


def test_standards_browse_and_detail(client):
    courses = client.get("/api/courses").json()
    assert {c["name"]: c["standards_count"] for c in courses} == {"Biology 1": 14, "Biology 2": 12, "Chemistry": 12}
    bio1 = next(c for c in courses if c["slug"] == "biology-1")
    assert bio1["source_document"]["published"] == "2026-07-13"

    found = client.get("/api/standards", params={"q": "carrying capacity"}).json()
    assert "B-LS2-1" in {s["code"] for s in found}
    only_bio1 = client.get("/api/standards", params={"course_id": bio1["id"]}).json()
    assert len(only_bio1) == 14
    assert client.get("/api/standards", params={"q": "Punnett"}).json()  # topic/terminology search
    with_family = client.get("/api/standards", params={"with_family_only": True}).json()
    assert sorted((s["course_slug"], s["code"]) for s in with_family) == [
        ("biology-1", "B-LS2-1"),
        ("biology-1", "B-LS3-3"),
        ("chemistry", "C-PS1-5"),
    ]

    detail = client.get(f"/api/standards/{_std(client, 'biology-1', 'B-LS3-3')['id']}").json()
    assert "Hardy-Weinberg" in detail["state_assessment_boundary"]
    assert detail["source_document"]["title"] == "Biology 1 Performance Targets for use 2026-2027"
    assert detail["families"][0]["key"] == "trait-probability"
    bio2 = client.get(f"/api/standards/{_std(client, 'biology-2', 'B-LS3-3')['id']}").json()
    assert bio2["repeat_of_biology_1"] is True and bio2["families"] == []

    bundles = client.get("/api/bundles", params={"course_id": bio1["id"]}).json()
    assert len(bundles) == 6
    fams = client.get("/api/families").json()
    assert all(t["observable_text"] for f in fams for t in f["templates"])


# ---- generation and bank ---------------------------------------------------------------------


def _generate(client, course_slug, code, family, **kw):
    std = _std(client, course_slug, code)
    body = {"standard_id": std["id"], "family_key": family, "quantity": 7, **kw}
    return std, body


@pytest.mark.parametrize(
    "course,code,family",
    [
        ("biology-1", "B-LS2-1", "population-carrying-capacity"),
        ("biology-1", "B-LS3-3", "trait-probability"),
        ("chemistry", "C-PS1-5", "reaction-rate"),
    ],
)
def test_preview_is_reproducible(client, course, code, family):
    _, body = _generate(client, course, code, family)
    first = client.post("/api/generate/preview", json=body).json()
    again = client.post("/api/generate/preview", json={**body, "seed": first["seed"]}).json()
    assert first == again
    assert sum(len(g["questions"]) for g in first["groups"]) == 7
    assert all(q["observable"]["text"] for g in first["groups"] for q in g["questions"])


def test_family_must_match_exact_standard(client):
    _, body = _generate(client, "biology-1", "B-LS2-1", "reaction-rate")
    assert client.post("/api/generate/preview", json=body).status_code == 422
    _, body = _generate(client, "biology-2", "B-LS3-3", "trait-probability")
    assert client.post("/api/generate/preview", json=body).status_code == 422
    _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity", doks=[4])
    assert client.post("/api/generate/preview", json=body).status_code == 422
    _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity")
    assert client.post("/api/generate/save", json=body).status_code == 422  # seed required


def _save(client, course="biology-1", code="B-LS2-1", family="population-carrying-capacity", seed="api-1", **kw):
    _, body = _generate(client, course, code, family, seed=seed, **kw)
    r = client.post("/api/generate/save", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_save_persists_with_provenance(client, db):
    from app.models import Question

    preview = client.post(
        "/api/generate/preview",
        json=_generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity", seed="prov")[1],
    ).json()
    saved = _save(client, seed="prov")
    assert len(saved["question_ids"]) == 7
    detail = client.get(f"/api/questions/{saved['question_ids'][0]}").json()
    prov = detail["provenance"]
    assert prov["seed"] == "prov" and prov["family"]["key"] == "population-carrying-capacity"
    assert prov["standard"]["code"] == "B-LS2-1" and prov["standard"]["use_year"] == "2026-2027"
    assert prov["source_document"]["published"] == "2026-07-13"
    assert prov["observable_performance"]["text"]
    assert detail["status"] == "generated" and detail["current"]["origin"] == "engine"
    assert detail["stimulus"]["body"] == preview["groups"][0]["stimulus"]
    stored = {q.template_key for q in db.scalars(select(Question).where(Question.id.in_(saved["question_ids"])))}
    assert stored == {q["template_key"] for q in preview["groups"][0]["questions"]}


def test_edit_versioning_and_restore(client):
    qid = _save(client, seed="edit")["question_ids"][0]
    q = client.get(f"/api/questions/{qid}").json()
    cur = q["current"]
    assert cur["question_type"] == "multiple_choice"
    choices = [{"text": c["text"], "correct": c["correct"], "rationale": c["rationale"]} for c in cur["choices"]]

    bad = client.post(
        f"/api/questions/{qid}/versions",
        json={"stem": cur["stem"], "dok": cur["dok"], "choices": [{**c, "correct": True} for c in choices]},
    )
    assert bad.status_code == 422
    same = client.post(
        f"/api/questions/{qid}/versions",
        json={"stem": cur["stem"], "dok": cur["dok"], "choices": choices, "explanation": cur["explanation"]},
    )
    assert same.status_code == 409

    edited = client.post(
        f"/api/questions/{qid}/versions",
        json={
            "stem": cur["stem"] + " (edited)",
            "dok": cur["dok"],
            "choices": choices,
            "explanation": cur["explanation"],
            "change_note": "clarify",
        },
    ).json()
    assert edited["current"]["version_no"] == 2 and edited["current"]["origin"] == "teacher_edit"
    assert [v["version_no"] for v in edited["versions"]] == [2, 1]
    assert edited["versions"][1]["stem"] == cur["stem"]  # original preserved

    restored = client.post(f"/api/questions/{qid}/restore/1").json()
    assert restored["current"]["version_no"] == 3 and restored["current"]["stem"] == cur["stem"]
    assert restored["current"]["origin"] == "engine"


def test_status_transitions(client):
    ids = _save(client, seed="status")["question_ids"]
    r = client.post(f"/api/questions/{ids[0]}/status", json={"to_status": "approved", "note": "looks good"})
    assert r.json()["status"] == "approved"
    assert client.post(f"/api/questions/{ids[0]}/status", json={"to_status": "rejected"}).status_code == 409
    bulk = client.post(
        "/api/questions/bulk-status", json={"question_ids": [ids[0], ids[1], 999999], "to_status": "rejected"}
    )
    assert bulk.json()["updated"] == [ids[1]]
    assert set(bulk.json()["skipped"]) == {str(ids[0]), "999999"}
    events = client.get(f"/api/questions/{ids[0]}").json()["status_events"]
    assert [e["to_status"] for e in events] == ["approved", "generated"]

    page = client.get("/api/questions", params={"status": "approved", "q": "B-LS2-1"}).json()
    assert page["total"] >= 1 and all(i["status"] == "approved" for i in page["items"])
    assert page["status_counts"].get("rejected", 0) >= 1


# ---- assessments -----------------------------------------------------------------------------


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


def test_assessment_builder_and_print(client):
    pop = _save(client, seed="assess-pop")["question_ids"]
    gen = _save(client, "biology-1", "B-LS3-3", "trait-probability", seed="assess-gen")["question_ids"]
    client.post(f"/api/questions/{gen[1]}/status", json={"to_status": "rejected"})

    a = client.post("/api/assessments", json={"title": "Unit 3 quiz", "instructions": "Show your work."}).json()
    aid = a["id"]
    # interleave: second population question should be grouped next to the first
    added = client.post(
        f"/api/assessments/{aid}/items", json={"question_ids": [pop[0], gen[0], pop[1], gen[1], pop[0]]}
    ).json()
    assert added["added"] == [pop[0], gen[0], pop[1]]
    assert set(added["skipped"]) == {str(gen[1])}  # duplicates in one request collapse
    again = client.post(f"/api/assessments/{aid}/items", json={"question_ids": [pop[0]]}).json()
    assert again["skipped"] == {str(pop[0]): "already in this assessment"}
    detail = client.get(f"/api/assessments/{aid}").json()
    assert [i["question_id"] for i in detail["items"]] == [pop[0], pop[1], gen[0]]
    assert {c["code"] for c in detail["standards_coverage"]} == {"B-LS2-1", "B-LS3-3"}
    assert sum(detail["dok_distribution"].values()) == 3

    # pinned version survives an edit until refreshed
    cur = client.get(f"/api/questions/{pop[0]}").json()["current"]
    client.post(
        f"/api/questions/{pop[0]}/versions",
        json={
            "stem": cur["stem"] + " Show your reasoning.",
            "dok": cur["dok"],
            "choices": [
                {"text": c["text"], "correct": c["correct"], "rationale": c["rationale"]} for c in cur["choices"]
            ],
            "explanation": cur["explanation"],
        },
    )
    item = client.get(f"/api/assessments/{aid}").json()["items"][0]
    assert (item["pinned_version_no"], item["latest_version_no"]) == (1, 2)
    refreshed = client.post(f"/api/assessments/{aid}/items/{item['id']}/refresh").json()
    assert refreshed["items"][0]["pinned_version_no"] == 2

    order = [i["id"] for i in refreshed["items"]][::-1]
    assert [
        i["id"] for i in client.put(f"/api/assessments/{aid}/items/order", json={"item_ids": order}).json()["items"]
    ] == order
    assert client.put(f"/api/assessments/{aid}/items/order", json={"item_ids": order[:1]}).status_code == 422

    student = client.get(f"/api/assessments/{aid}/print", params={"variant": "student"}).json()
    keys = set(_all_keys(student))
    assert not keys & {"correct", "rationale", "answer", "explanation", "teacher_edited", "standards", "parameters"}
    text = json.dumps(student)
    teacher = client.get(f"/api/assessments/{aid}/print", params={"variant": "teacher"}).json()
    for block in teacher["blocks"]:
        for q in block["questions"]:
            assert q["answer"]
            if q["choices"]:
                correct = next(c for c in q["choices"] if c["correct"])
                assert f"{correct['label']}. {correct['text']}" == q["answer"]
                assert "Correct" not in text and correct["rationale"] not in text
    assert [q["number"] for b in student["blocks"] for q in b["questions"]] == [1, 2, 3]
    assert student["question_count"] == 3 and len(student["blocks"]) == 2  # one stimulus per block
    assert teacher["standards"] and teacher["blocks"][0]["questions"][0]["teacher_edited"] in (True, False)

    assert client.delete(f"/api/assessments/{aid}").status_code == 204
    assert client.get(f"/api/assessments/{aid}").status_code == 404
