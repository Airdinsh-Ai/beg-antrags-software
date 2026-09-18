def test_login_with_correct_credentials_returns_token(client, berater_user):
    response = client.post(
        "/auth/login", json={"email": berater_user.email, "password": "test-passwort-123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_with_wrong_password_returns_401(client, berater_user):
    response = client.post(
        "/auth/login", json={"email": berater_user.email, "password": "falsch"}
    )
    assert response.status_code == 401


def test_me_without_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401 or response.status_code == 403


def test_me_with_token_returns_current_user(client, auth_headers, berater_user):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == berater_user.email
    assert body["role"] == "beraterfirma_mitarbeiter"


def test_logout_returns_204(client, auth_headers):
    response = client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 204
