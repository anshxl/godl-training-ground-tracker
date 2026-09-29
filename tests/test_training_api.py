"""
Tests for the read-only training HTTP endpoint (handlers/training_api.py).
Uses aiohttp.test_utils with asyncio.run; no pytest plugins needed.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from aiohttp.test_utils import TestClient, TestServer

from handlers.training_api import make_app, start_training_api

TOKEN = "s3cret-token"


def seed(db):
    db.add_or_update_player("111", "Alpha")
    db.add_or_update_player("222", "Bravo")
    for discord_id, day, name in [
        ("111", 2, "a.png"), ("111", 2, "b.png"), ("111", 5, "c.png"),
        ("222", 3, "d.png"),
    ]:
        db.clock = lambda d=day: datetime(2026, 9, d, 16, 0, tzinfo=timezone.utc)
        db.log_submission(discord_id, f"https://cdn.example.com/{name}", name)
    db.clock = lambda: datetime(2026, 8, 20, 16, 0, tzinfo=timezone.utc)
    db.log_submission("222", "https://cdn.example.com/e.png", "e.png")


def request(db, path, headers=None):
    """Run one GET against the app; return (status, parsed JSON or text)."""
    async def go():
        async with TestClient(TestServer(make_app(db, TOKEN))) as client:
            resp = await client.get(path, headers=headers or {})
            if resp.content_type == "application/json":
                return resp.status, await resp.json()
            return resp.status, await resp.text()
    return asyncio.run(go())


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_200_with_token(temp_db):
    seed(temp_db)
    status, body = request(temp_db, "/training?month=2026-09", AUTH)

    assert status == 200
    assert body == {
        "month": "2026-09",
        "months": ["2026-08", "2026-09"],
        "players": [
            {"username": "Alpha", "sessions": 3, "days_trained": 2},
            {"username": "Bravo", "sessions": 1, "days_trained": 1},
        ],
        "daily": [
            {"date": "2026-09-02", "username": "Alpha", "sessions": 2},
            {"date": "2026-09-03", "username": "Bravo", "sessions": 1},
            {"date": "2026-09-05", "username": "Alpha", "sessions": 1},
        ],
    }


def test_no_private_fields_in_body(temp_db):
    seed(temp_db)
    status, body = request(temp_db, "/training?month=2026-09", AUTH)

    assert status == 200
    text = str(body)
    for forbidden in ("image_url", "filename", "discord_id", "cdn.example.com", "111", "222", ".png"):
        assert forbidden not in text


def test_401_without_token(temp_db):
    status, _ = request(temp_db, "/training?month=2026-09")
    assert status == 401


def test_401_with_wrong_token(temp_db):
    status, _ = request(temp_db, "/training?month=2026-09", {"Authorization": "Bearer nope"})
    assert status == 401


def test_401_with_non_bearer_scheme(temp_db):
    status, _ = request(temp_db, "/training?month=2026-09", {"Authorization": TOKEN})
    assert status == 401


def test_400_missing_month(temp_db):
    status, _ = request(temp_db, "/training", AUTH)
    assert status == 400


def test_400_bad_month(temp_db):
    for bad in ("2026-13", "2026-00", "2026-9", "abc", "2026-09-01"):
        status, _ = request(temp_db, f"/training?month={bad}", AUTH)
        assert status == 400, bad


def test_start_does_nothing_without_token(temp_db, monkeypatch):
    monkeypatch.delenv("TRAINING_API_TOKEN", raising=False)
    bot = SimpleNamespace(db=temp_db, training_api_runner=None)

    runner = asyncio.run(start_training_api(bot))

    assert runner is None
    assert bot.training_api_runner is None
