"""Spec §2 / §12: every endpoint, called with the wrong role, returns 403.

Step 1 has few endpoints; this test walks every route automatically, so endpoints added in later
steps are covered as soon as they exist. The full §2 table walk-through is extended step by step.
"""

from fastapi.routing import APIRoute

from app.main import ROUTERS

ROLES = ("worker", "manager", "md")

# Routes not tied to a user role. Everything else must declare its roles with require_roles().
PUBLIC = {
    ("POST", "/api/auth/password-login"),
    ("POST", "/api/auth/passkey/options"),
    ("POST", "/api/auth/passkey/login"),
    ("POST", "/api/auth/logout"),  # any signed-in user
    ("GET", "/api/auth/me"),
    ("GET", "/api/invites/{token}"),  # the invite token is the credential
    ("POST", "/api/invites/{token}/options"),
    ("POST", "/api/invites/{token}/register"),
    ("POST", "/api/kiosk/pair"),  # the single-use TV setup token is the credential
    ("GET", "/api/kiosk/code"),  # the TV's kiosk cookie is the credential
}


def _allowed_roles(route: APIRoute):
    stack = [route.dependant]
    while stack:
        d = stack.pop()
        roles = getattr(d.call, "allowed_roles", None)
        if roles is not None:
            return roles
        stack.extend(d.dependencies)
    return None


def _api_routes():
    for router in ROUTERS:
        for r in router.routes:
            assert isinstance(r, APIRoute) and r.path.startswith("/api/")
            for m in r.methods:
                yield m, r


def test_md_calling_a_worker_endpoint_gets_403(client, md, make_user, session_for):
    """Step 1 done check."""
    from tests.conftest import login_md

    login_md(client)
    r = client.get("/api/me/today")
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "forbidden"


def test_nobody_signed_in_gets_401(client):
    assert client.get("/api/me/today").status_code == 401


def test_worker_and_manager_can_see_their_own_day(client, make_user, session_for):
    for role in ("worker", "manager"):
        token, _ = session_for(make_user(f"A {role}", role))
        client.cookies.set("att_session", token)
        r = client.get("/api/me/today")
        assert r.status_code == 200, role
        body = r.json()
        assert body["work_date"] == "2026-11-16"
        assert body["working_day"] is True
        assert body["schedule"] == {"start": "08:00", "grace_minutes": 10, "on_time_until": "08:10",
                                    "close": "17:00"}
        assert body["date"] == "Monday 16 November"


def test_every_route_declares_its_roles():
    missing = [(m, r.path) for m, r in _api_routes()
               if (m, r.path) not in PUBLIC and _allowed_roles(r) is None]
    assert missing == []


def test_every_route_returns_403_for_each_wrong_role(client, make_user, session_for):
    users = {role: session_for(make_user(f"Someone {role}", role,
                                         email=f"{role}@company.test" if role == "md" else None,
                                         password="x" * 12 if role == "md" else None))
             for role in ROLES}
    checked = 0
    for method, route in _api_routes():
        roles = _allowed_roles(route)
        if roles is None:
            continue
        path = route.path.replace("{", "").replace("}", "")  # dummy path params
        for role in set(ROLES) - set(roles):
            token, csrf = users[role]
            client.cookies.set("att_session", token)
            r = client.request(method, path, headers={"X-CSRF-Token": csrf}, json={})
            assert r.status_code == 403, (method, route.path, role, r.status_code)
            checked += 1
    assert checked >= 1
