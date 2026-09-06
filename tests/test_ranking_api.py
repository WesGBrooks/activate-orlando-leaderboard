from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_and_leaderboard_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("FORCE_DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_MODE_FALLBACK", "true")
    monkeypatch.setenv("FRIENDS_PATH", str(tmp_path / "friends.json"))
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    get_settings.cache_clear()

    client = TestClient(app)
    assert client.get("/healthz").json()["status"] == "ok"

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Activate" in resp.text

    api = client.get("/api/leaderboard")
    assert api.status_code == 200
    payload = api.json()
    assert payload["location"]["id"] == 42
    assert payload["location"]["slug"] == "pointe-orlando"
    assert len(payload["players"]) >= 1
