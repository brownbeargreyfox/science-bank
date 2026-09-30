"""The extracted generation service behaves exactly like the preview endpoint."""

from tests.test_api import _generate


def test_service_output_matches_the_preview_endpoint(client, db):
    from app.schemas import GenerateRequest
    from app.services.generation import generate_for_request

    _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity", seed="svc")
    api_out = client.post("/api/generate/preview", json=body).json()
    _, family, out = generate_for_request(db, GenerateRequest(**body), "svc")
    assert family.key == "population-carrying-capacity"
    assert [g["parameters"] for g in out["groups"]] == [g["parameters"] for g in api_out["groups"]]
    assert [q["stem"] for g in out["groups"] for q in g["questions"]] == [
        q["stem"] for g in api_out["groups"] for q in g["questions"]
    ]
    assert out["options"]["generation_mode"] == "classroom"
