from app import create_app


def make_client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_healthz():
    client = make_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_get():
    client = make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"CloudMart Sample App" in response.data


def test_index_post_escapes_name():
    client = make_client()
    response = client.post("/", data={"name": "<script>alert(1)</script>"})
    assert response.status_code == 200
    assert b"<script>alert(1)</script>" not in response.data


def test_about():
    client = make_client()
    response = client.get("/about")
    assert response.status_code == 200
    assert b"About CloudMart" in response.data


def test_security_headers():
    client = make_client()
    response = client.get("/healthz")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
