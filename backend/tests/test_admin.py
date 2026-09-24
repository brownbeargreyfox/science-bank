from sqlalchemy import select

from tests.conftest import login_as


def test_admin_routes_require_admin(anon):
    for who in ("regular", "power"):
        login_as(anon, who)
        assert anon.get("/api/admin/users").status_code == 403
        assert anon.patch("/api/admin/settings", json={"registration_open": False}).status_code == 403
    login_as(anon, "admin")
    users = anon.get("/api/admin/users").json()
    assert {"nina", "pat", "reg"} <= {u["username"] for u in users}
    assert "password_hash" not in users[0]


def test_create_update_and_reset_password(anon, db):
    from app.models import AuditEvent

    login_as(anon, "admin")
    weak = {"username": "newteach", "password": "short", "role": "regular"}
    assert anon.post("/api/admin/users", json=weak).status_code == 422
    body = {"username": "newteach", "password": "a fine long password", "role": "regular"}
    r = anon.post("/api/admin/users", json=body)
    assert r.status_code == 201
    uid = r.json()["id"]
    assert anon.post("/api/admin/users", json={**body, "username": "NEWTEACH"}).status_code == 409
    assert anon.patch(f"/api/admin/users/{uid}", json={"role": "power"}).json()["role"] == "power"
    assert anon.post(f"/api/admin/users/{uid}/password", json={"password": "another long password"}).status_code == 204
    anon.post("/api/auth/logout")
    creds = {"username": "newteach", "password": "another long password"}
    assert anon.post("/api/auth/login", json=creds).status_code == 200
    db.expire_all()
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == str(uid))).all())
    assert {"admin.user_create", "admin.user_update", "admin.password_reset"} <= actions
    details = " ".join(str(d) for d in db.scalars(select(AuditEvent.detail).where(AuditEvent.target_id == str(uid))))
    assert "another long password" not in details and "a fine long password" not in details and "$2b$" not in details


def test_demotion_applies_to_existing_session(anon, db):
    from app.core.security import hash_password
    from app.models import User

    db.add(User(username="temp-admin", password_hash=hash_password("temporary password"), role="admin"))
    db.commit()
    anon.post("/api/auth/logout")
    anon.post("/api/auth/login", json={"username": "temp-admin", "password": "temporary password"})
    assert anon.get("/api/admin/users").status_code == 200
    u = db.scalar(select(User).where(User.username == "temp-admin"))
    u.role = "regular"
    db.commit()
    assert anon.get("/api/admin/users").status_code == 403


def test_last_admin_guard(anon, db):
    from app.models import User

    me = login_as(anon, "admin")
    others = db.scalars(select(User).where(User.role == "admin", User.id != me["id"], User.is_active)).all()
    for o in others:  # make nina the only active admin for this test
        o.is_active = False
    db.commit()
    try:
        assert anon.patch(f"/api/admin/users/{me['id']}", json={"role": "power"}).status_code == 409
        assert anon.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}).status_code == 409
        assert anon.get("/api/auth/me").json()["role"] == "admin"
    finally:
        for o in others:
            o.is_active = True
        db.commit()


def test_registration_toggle(anon):
    login_as(anon, "admin")
    assert anon.patch("/api/admin/settings", json={"registration_open": False}).json() == {"registration_open": False}
    try:
        anon.post("/api/auth/logout")
        assert anon.get("/api/auth/registration-status").json() == {"registration_open": False}
        blocked = {"username": "blocked", "password": "long enough password"}
        assert anon.post("/api/auth/register", json=blocked).status_code == 403
    finally:
        login_as(anon, "admin")
        anon.patch("/api/admin/settings", json={"registration_open": True})


# ---- CLI ---------------------------------------------------------------------------------------


def test_cli_set_role_and_list_users(database, capsys, db):
    from app import cli
    from app.models import AuditEvent, User

    assert cli.main(["set-role", "--username", "REG2", "--role", "power"]) == 0
    db.expire_all()
    assert db.scalar(select(User.role).where(User.username == "reg2")) == "power"
    assert cli.main(["set-role", "--username", "reg2", "--role", "regular"]) == 0
    assert cli.main(["set-role", "--username", "nobody", "--role", "admin"]) == 1
    assert cli.main(["list-users"]) == 0
    out = capsys.readouterr().out
    assert "nina" in out and "admin" in out
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "cli.set_role")) is not None


def test_cli_set_password_requires_username_once_users_exist(database, monkeypatch):
    import io

    from app import cli

    monkeypatch.setattr("sys.stdin", io.StringIO("long enough password\n"))
    assert cli.main(["set-password", "--password-stdin"]) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("tooshort\n"))
    assert cli.main(["set-password", "--username", "reg", "--password-stdin"]) == 1


def test_cli_set_active_respects_last_admin(database, db):
    from app import cli
    from app.models import User

    admins = db.scalars(select(User).where(User.role == "admin", User.is_active).order_by(User.id)).all()
    for a in admins[1:]:
        a.is_active = False
    db.commit()
    try:
        assert cli.main(["set-active", "--username", admins[0].username, "--active", "false"]) == 1
        db.expire_all()
        assert db.get(User, admins[0].id).is_active is True
    finally:
        for a in admins[1:]:
            a.is_active = True
        db.commit()
