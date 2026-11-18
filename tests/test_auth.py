from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from starlette.testclient import TestClient

from muzbingo.ui.auth import COOKIE_NAME, TokenAuthMiddleware

TOKEN = "secret-token"


def make_client(check_host=True) -> TestClient:
    app = FastAPI()

    @app.get("/page")
    def page():
        return PlainTextResponse("hello")

    app.add_middleware(TokenAuthMiddleware, token=TOKEN, check_host=check_host)
    return TestClient(app, base_url="http://localhost:8080")


def test_requests_without_token_are_refused():
    client = make_client()
    assert client.get("/page").status_code == 403
    assert client.get("/page?token=wrong").status_code == 403


def test_token_link_sets_cookie_and_strips_token():
    client = make_client()
    response = client.get("/page?token=secret-token&tab=cards", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/page?tab=cards"
    assert COOKIE_NAME in response.cookies

    assert client.get("/page").text == "hello"  # the cookie is kept by the client


def test_host_header_is_checked():
    client = make_client()
    client.cookies.set(COOKIE_NAME, TOKEN)
    assert client.get("/page", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/page", headers={"host": "127.0.0.1:8080"}).status_code == 200

    lan = make_client(check_host=False)  # --host 0.0.0.0: any host, token still needed
    assert lan.get("/page", headers={"host": "192.168.1.5:8080"}).status_code == 403
