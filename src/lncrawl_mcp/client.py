"""Thin async client for the Lightnovel Crawler server REST API."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import httpx

JOB_STATUS = {0: "pending", 1: "running", 2: "success", 3: "failed", 4: "canceled", 5: "paused"}
FINISHED_STATUSES = {2, 3, 4}
POLL_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 60


class LncrawlError(Exception):
    pass


class LncrawlClient:
    def __init__(self, base_url: str, token: str = "", email: str = "", password: str = "") -> None:
        self._token = token
        self._email = email
        self._password = password
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=REQUEST_TIMEOUT_SECONDS)

    @classmethod
    def from_env(cls) -> LncrawlClient:
        return cls(
            base_url=os.environ.get("LNCRAWL_URL", "http://127.0.0.1:8181"),
            token=os.environ.get("LNCRAWL_TOKEN", ""),
            email=os.environ.get("LNCRAWL_EMAIL", ""),
            password=os.environ.get("LNCRAWL_PASSWORD", ""),
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self._token:
            await self._login()
        response = await self._send(method, path, **kwargs)
        if response.status_code == 401 and self._email:
            await self._login()
            response = await self._send(method, path, **kwargs)
        if response.is_error:
            raise LncrawlError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")
        return response.json()

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token}"}
        return await self._http.request(method, path, headers=headers, **kwargs)

    async def _login(self) -> None:
        if not (self._email and self._password):
            raise LncrawlError("Set LNCRAWL_TOKEN, or LNCRAWL_EMAIL and LNCRAWL_PASSWORD")
        response = await self._http.post(
            "/api/auth/login", json={"email": self._email, "password": self._password}
        )
        if response.is_error:
            raise LncrawlError(f"Login failed: {response.status_code} {response.text[:200]}")
        self._token = response.json()["token"]

    async def create_job(self, name: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/api/job/create/{name}", json=body)

    async def wait_for_job(self, job: dict[str, Any], wait_seconds: float) -> dict[str, Any]:
        deadline = time.monotonic() + wait_seconds
        while job["status"] not in FINISHED_STATUSES and time.monotonic() < deadline:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            job = await self.request("GET", f"/api/job/{job['id']}")
        return job

    async def save_artifact(self, artifact: dict[str, Any], directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / artifact["file_name"]
        url = f"/static/{artifact['output_file']}"
        async with self._http.stream("GET", url, params={"token": self._token}) as response:
            if response.is_error:
                raise LncrawlError(f"GET {url} -> {response.status_code}")
            with target.open("wb") as file:
                async for chunk in response.aiter_bytes():
                    file.write(chunk)
        return target


def summarize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "title": job["job_title"],
        "status": JOB_STATUS[job["status"]],
        "finished": job["status"] in FINISHED_STATUSES,
        "done": job["done"],
        "failed": job["failed"],
        "total": job["total"],
        "error": job["error"],
        "extra": job["extra"],
    }
