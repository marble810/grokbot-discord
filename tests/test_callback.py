from aiohttp.test_utils import TestClient, TestServer

from grokbot_discord.callback import RateLimit, build_app

AUTH = {"Authorization": "Bearer s3cret"}


async def _client(limit=100):
    seen = []

    async def on_reply(cid, text):
        if cid != "known":
            return False
        seen.append((cid, text))
        return True

    return TestClient(TestServer(build_app("s3cret", on_reply, RateLimit(limit)))), seen


async def test_auth_and_correlation():
    client, seen = await _client()
    async with client:
        assert (await client.get("/health")).status == 200
        assert (await client.post("/reply", json={"correlation_id": "known"})).status == 401
        bad = {"Authorization": "Bearer nope"}
        assert (await client.post("/reply", json={}, headers=bad)).status == 401
        r = await client.post(
            "/reply", json={"correlation_id": "forged", "channel_id": "1", "text": "hi"},
            headers=AUTH,
        )
        assert r.status == 404
        r = await client.post(
            "/reply", json={"correlation_id": "known", "text": "hi"}, headers=AUTH
        )
        assert r.status == 200
        assert seen == [("known", "hi")]


async def test_rate_limit():
    client, _ = await _client(limit=2)
    async with client:
        codes = [(await client.post("/reply", json={}, headers=AUTH)).status for _ in range(3)]
        assert codes[-1] == 429
