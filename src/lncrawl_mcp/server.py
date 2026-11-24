"""MCP server exposing a Lightnovel Crawler server as tools."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import LncrawlClient, summarize_job

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

DEFAULT_WAIT_SECONDS = 60
MAX_SEARCH_RESULTS = 50
NOVEL_FIELDS = ("id", "title", "authors", "domain", "url", "language", "chapter_count", "tags")
CHAPTER_FIELDS = ("id", "serial", "title", "is_available")

mcp = FastMCP("lncrawl")
client = LncrawlClient.from_env()


def pick(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item.get(field) for field in fields}


@mcp.tool()
async def list_sources(query: str = "", language: str = "", can_search: bool = False) -> list[dict]:
    """List supported novel sites. Filter by domain substring, language code, or search support."""
    sources = await client.request("GET", "/api/sources", params={"skip_rejected": True})
    matches = [
        source
        for source in sources
        if query.lower() in source["domain"].lower()
        and (not language or source.get("language") == language)
        and (not can_search or source.get("can_search"))
        and not source.get("is_disabled")
    ]
    return [pick(s, ("domain", "url", "language", "can_search", "has_mtl", "can_login")) for s in matches]


@mcp.tool()
async def search_novels(
    query: str, domain: str = "", wait_seconds: int = DEFAULT_WAIT_SECONDS
) -> dict:
    """Search novels by title across every searchable source, or one `domain`.

    Waits up to `wait_seconds`; if `finished` is false, call get_job with the job id
    for more results. Pass a result `url` to add_novel.
    """
    body = {"query": query, "domain": domain or None}
    job = await client.create_job("search-sources", body)
    job = await client.wait_for_job(job, wait_seconds)
    results = job["extra"].get("search_results", [])
    return {
        "job": summarize_job(job) | {"extra": None},
        "total_results": len(results),
        "results": [pick(r, ("title", "url", "info")) for r in results[:MAX_SEARCH_RESULTS]],
    }


@mcp.tool()
async def add_novel(url: str, wait_seconds: int = DEFAULT_WAIT_SECONDS) -> dict:
    """Fetch a novel's metadata and chapter list from its page URL. Returns its `novel_id`."""
    job = await client.create_job("fetch-novels", {"urls": [url]})
    job = await client.wait_for_job(job, wait_seconds)
    return {"novel_id": job["extra"].get("novel_id"), "job": summarize_job(job)}


@mcp.tool()
async def list_novels(search: str = "", limit: int = 20, offset: int = 0) -> dict:
    """List novels already in the server's library, optionally filtered by title."""
    params = {"search": search, "limit": limit, "offset": offset}
    page = await client.request("GET", "/api/novels", params=params)
    return {"total": page["total"], "novels": [pick(n, NOVEL_FIELDS) for n in page["items"]]}


@mcp.tool()
async def get_novel(novel_id: str) -> dict:
    """Novel details with synopsis and its exported e-book files (artifacts)."""
    novel = await client.request("GET", f"/api/novel/{novel_id}")
    artifacts = await client.request("GET", f"/api/novel/{novel_id}/artifacts")
    return {
        "novel": pick(novel, NOVEL_FIELDS) | {"synopsis": novel.get("synopsis")},
        "artifacts": [pick(a, ("id", "format", "language", "volume", "file_name", "file_size", "is_available")) for a in artifacts],
    }


@mcp.tool()
async def list_chapters(novel_id: str, offset: int = 0, limit: int = 50) -> dict:
    """List chapters of a novel. `is_available` means the content is downloaded."""
    params = {"offset": offset, "limit": limit}
    page = await client.request("GET", f"/api/novel/{novel_id}/chapters", params=params)
    return {"total": page["total"], "chapters": [pick(c, CHAPTER_FIELDS) for c in page["items"]]}


@mcp.tool()
async def read_chapter(
    chapter_id: str, language: str = "", auto_fetch: bool = True, wait_seconds: int = DEFAULT_WAIT_SECONDS
) -> dict:
    """Read a chapter's text. Downloads it first when missing and `auto_fetch` is true.

    `next_id` and `previous_id` are chapter ids for paging.
    """
    params: dict[str, Any] = {"auto_fetch": auto_fetch}
    if language:
        params["language"] = language
    path = f"/api/chapter/{chapter_id}/read"
    read = await client.request("GET", path, params=params)
    if read["content"] is None and read["job"]:
        await client.wait_for_job(read["job"], wait_seconds)
        read = await client.request("GET", path, params=params)
    return {
        "title": read["chapter"]["title"],
        "serial": read["chapter"]["serial"],
        "content": read["content"],
        "word_count": read["word_count"],
        "next_id": read["next_id"],
        "previous_id": read["previous_id"],
        "job": summarize_job(read["job"]) if read["job"] else None,
    }


@mcp.tool()
async def download_missing_chapters(novel_id: str, wait_seconds: int = DEFAULT_WAIT_SECONDS) -> dict:
    """Download every chapter not yet downloaded. Long novels outlive `wait_seconds`: poll get_job."""
    job = await client.create_job("fetch-missing", {"novel_id": novel_id})
    return summarize_job(await client.wait_for_job(job, wait_seconds))


@mcp.tool()
async def update_novel(novel_id: str, wait_seconds: int = DEFAULT_WAIT_SECONDS) -> dict:
    """Refresh metadata, download new chapters, then rebuild the e-books."""
    job = await client.create_job("fetch-latest", {"novel_id": novel_id})
    return summarize_job(await client.wait_for_job(job, wait_seconds))


@mcp.tool()
async def make_ebook(
    novel_id: str,
    formats: list[str] | None = None,
    language: str = "",
    wait_seconds: int = DEFAULT_WAIT_SECONDS,
) -> dict:
    """Build e-book files from downloaded chapters. Formats: epub, txt, json; pdf, mobi, azw3,
    kepub, docx and others need Calibre on the server. Defaults to epub."""
    body = {"novel_id": novel_id, "formats": formats or ["epub"], "language": language or None}
    job = await client.create_job("make-artifacts", body)
    job = await client.wait_for_job(job, wait_seconds)
    children = await client.request("GET", "/api/jobs", params={"parent_job_id": job["id"]})
    child_ids = {child["id"] for child in children["items"]}
    listing = await client.request("GET", "/api/artifacts", params={"novel_id": novel_id})
    built = [a for a in listing["items"] if a["job_id"] in child_ids]
    return {"job": summarize_job(job), "artifacts": [pick(a, ("id", "format", "file_name", "file_size")) for a in built]}


@mcp.tool()
async def save_ebook(artifact_id: str, directory: str = "") -> dict:
    """Download an e-book file to a local directory (default `$LNCRAWL_DOWNLOAD_DIR` or ./downloads)."""
    artifact = await client.request("GET", f"/api/artifact/{artifact_id}")
    target_dir = Path(directory or os.environ.get("LNCRAWL_DOWNLOAD_DIR", "downloads"))
    path = await client.save_artifact(artifact, target_dir)
    return {"path": str(path.resolve()), "size": path.stat().st_size}


@mcp.tool()
async def get_job(job_id: str, wait_seconds: int = 0) -> dict:
    """Job progress. Set `wait_seconds` to block until it finishes. Search jobs include results in `extra`."""
    job = await client.request("GET", f"/api/job/{job_id}")
    return summarize_job(await client.wait_for_job(job, wait_seconds))


@mcp.tool()
async def cancel_job(job_id: str) -> dict:
    """Cancel a running job."""
    await client.request("POST", f"/api/job/{job_id}/cancel")
    return summarize_job(await client.request("GET", f"/api/job/{job_id}"))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
