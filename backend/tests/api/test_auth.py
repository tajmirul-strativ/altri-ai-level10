"""Sign-in with a seeded-user picker and a signed session cookie (design.md §5)."""

from fastapi.testclient import TestClient

from tests.conftest import ApiFactory


def test_user_picker_lists_seeded_users_without_signing_in(client: TestClient) -> None:
    response = client.get("/api/auth/users")

    assert response.status_code == 200
    users = response.json()
    assert [u["id"] for u in users] == [f"u{n}" for n in range(1, 10)]
    assert users[0] == {"id": "u1", "name": "Avery Admin", "role": "admin"}


def test_login_sets_an_http_only_session_cookie(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"user_id": "u2"})

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_me_returns_the_signed_in_user_and_company_time_zone(api: ApiFactory) -> None:
    response = api("u2").get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": "u2",
        "name": "Blake Brooks",
        "email": "blake@acme.test",
        "role": "team_member",
        "company": {"id": "co_1", "name": "Acme Logistics", "timezone": "America/Chicago"},
    }


def test_login_with_unknown_user_is_refused(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"user_id": "u99"})

    assert response.status_code == 401


def test_me_without_session_is_401(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_session_cookie_is_401(api: ApiFactory) -> None:
    c = api("u5")
    session = c.cookies.get("l10_session")
    assert session
    # Try to become the Admin by editing the cookie's payload.
    c.cookies.set("l10_session", session.replace("u5", "u1"))

    assert c.get("/api/auth/me").status_code == 401


def test_client_cannot_choose_user_by_header(api: ApiFactory) -> None:
    response = api(None).get("/api/auth/me", headers={"X-User-Id": "u1"})

    assert response.status_code == 401


def test_logout_ends_the_session(api: ApiFactory) -> None:
    c = api("u2")

    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401
