import httpx
import pytest

from lncrawl_mcp.client import LncrawlClient, LncrawlError

JOB = {"id": "j1", "status": 0}


def make_client(handler) -> LncrawlClient:
    client = LncrawlClient("http://lncrawl.test", email="a@b.c", password="pw")
    client._http = httpx.AsyncClient(
        base_url="http://lncrawl.test", transport=httpx.MockTransport(handler)
    )
    return client


async def test_relogs_in_after_expired_token():
    logins = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            logins.append(1)
            return httpx.Response(200, json={"token": f"t{len(logins)}"})
        if request.headers["authorization"] == "Bearer t1":
            return httpx.Response(401, text="expired")
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert await client.request("GET", "/api/jobs") == {"ok": True}
    assert len(logins) == 2


async def test_wait_for_job_stops_when_finished():
    states = iter([1, 2])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": "t"})
        return httpx.Response(200, json={**JOB, "status": next(states)})

    client = make_client(handler)
    job = await client.wait_for_job(JOB, wait_seconds=30)
    assert job["status"] == 2


async def test_error_status_raises():
    client = make_client(lambda request: httpx.Response(200, json={"token": "t"}) if "login" in request.url.path else httpx.Response(500, text="boom"))
    with pytest.raises(LncrawlError, match="500"):
        await client.request("GET", "/api/novels")


async def test_save_artifact_ignores_path_in_file_name(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"epub-bytes")

    client = make_client(handler)
    artifact = {"file_name": "../../escape.epub", "output_file": "novels/n/artifacts/a.epub"}
    saved = await client.save_artifact(artifact, tmp_path / "dl")
    assert saved == tmp_path / "dl" / "escape.epub"
    assert saved.read_bytes() == b"epub-bytes"
    assert not (tmp_path / "escape.epub").exists()
