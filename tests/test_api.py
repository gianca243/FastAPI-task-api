NAME = "omggianca"
PASSWORD = "omgomg1omg"


def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signup_and_login(client):
    response = client.post("/signup", json={"name": NAME, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["name"] == NAME

    response_login = client.post("/login", json={"name": NAME, "password": PASSWORD})

    assert response_login.status_code == 200
    assert response_login.json()["token_type"] == "bearer"
    assert "access_token" in response_login.json()


def test_login_wrong_password(client):
    response = client.post("/signup", json={"name": NAME, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["name"] == NAME

    response_login = client.post("/login", json={"name": NAME, "password": PASSWORD + "omg"})
    assert response_login.status_code == 401
    assert response_login.json()["detail"] == "Incorrect username or password"


def test_signup_does_not_return_password(client):
    response = client.post("/signup", json={"name": NAME, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["name"] == NAME
    assert "password" not in response.json()


def test_signup_duplicate_user(client):
    response = client.post("/signup", json={"name": NAME, "password": PASSWORD})
    response_v2 = client.post("/signup", json={"name": NAME, "password": PASSWORD})
    assert response.status_code == 200
    assert response_v2.status_code == 409
    assert response_v2.json()["detail"] == "The user is duplicated"


def test_invalid_token(client):
    token_header = signup_and_login(client)
    token_header["Authorization"] += "omg"
    response = client.get("/task", headers=token_header)
    assert response.status_code == 401


def test_malformed_token(client):
    response = client.get("/task", headers={"Authorization": "Bearer esto-no-es-un-jwt"})

    assert response.status_code == 401


def signup_and_login(_client):
    _ = _client.post("/signup", json={"name": NAME, "password": PASSWORD})
    response_login = _client.post("/login", json={"name": NAME, "password": PASSWORD})
    token = response_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
