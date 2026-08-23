def test_register_new_user_succeeds(client):
    response = client.post("/register", json={
        "email": "alice@example.com",
        "password": "securepassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_fails(client):
    client.post("/register", json={
        "email": "bob@example.com",
        "password": "password123"
    })
    response = client.post("/register", json={
        "email": "bob@example.com",
        "password": "differentpassword"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_with_correct_credentials_succeeds(client):
    client.post("/register", json={
        "email": "carol@example.com",
        "password": "mypassword123"
    })
    response = client.post("/login", json={
        "email": "carol@example.com",
        "password": "mypassword123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_fails(client):
    client.post("/register", json={
        "email": "dave@example.com",
        "password": "correctpassword"
    })
    response = client.post("/login", json={
        "email": "dave@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_login_with_nonexistent_email_fails(client):
    response = client.post("/login", json={
        "email": "doesnotexist@example.com",
        "password": "whatever"
    })
    assert response.status_code == 401


def test_upload_without_token_fails(client):
    response = client.post("/upload")
    assert response.status_code == 401


def test_meetings_list_without_token_fails(client):
    response = client.get("/meetings")
    assert response.status_code == 401


def test_meetings_list_with_valid_token_returns_empty_list(client):
    register_response = client.post("/register", json={
        "email": "erin@example.com",
        "password": "password123"
    })
    token = register_response.json()["access_token"]

    response = client.get("/meetings", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_nonexistent_meeting_returns_404(client):
    register_response = client.post("/register", json={
        "email": "frank@example.com",
        "password": "password123"
    })
    token = register_response.json()["access_token"]

    response = client.get("/meetings/999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404