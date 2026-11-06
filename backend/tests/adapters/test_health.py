from fastapi.testclient import TestClient

from log_whisperer.bootstrap.container import build_app
from log_whisperer.bootstrap.settings import Settings


def test_healthz_returns_ok() -> None:
    client = TestClient(build_app(Settings.from_env({})))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
