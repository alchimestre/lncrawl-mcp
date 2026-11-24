# lncrawl-mcp

MCP server for [Lightnovel Crawler](https://github.com/lncrawl/lightnovel-crawler). It drives a running `lncrawl server` through its REST API: search 300+ sources, add novels, read chapters, export e-books.

## Install

1. Run an lncrawl server: `lncrawl server --port 8181`
2. Install this server: `uv tool install .`
3. Register it with your MCP client:

```json
{
  "mcpServers": {
    "lncrawl": {
      "command": "lncrawl-mcp",
      "env": {
        "LNCRAWL_URL": "http://127.0.0.1:8181",
        "LNCRAWL_EMAIL": "you@example.com",
        "LNCRAWL_PASSWORD": "change-me"
      }
    }
  }
}
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `LNCRAWL_URL` | `http://127.0.0.1:8181` | Server base URL |
| `LNCRAWL_TOKEN` | none | API token; replaces email and password |
| `LNCRAWL_EMAIL`, `LNCRAWL_PASSWORD` | none | Login; renewed on expiry |
| `LNCRAWL_DOWNLOAD_DIR` | `./downloads` | Where `save_ebook` writes |

## Tools

| Tool | Does |
|------|------|
| `list_sources` | Supported sites, filtered by domain, language, search support |
| `search_novels` | Title search across sources, or one `domain` |
| `add_novel` | Fetch metadata and chapter list from a novel URL |
| `list_novels`, `get_novel`, `list_chapters` | Browse the server's library |
| `read_chapter` | Chapter text; downloads it first when missing |
| `download_missing_chapters` | Download all undownloaded chapters |
| `update_novel` | Refresh metadata, download new chapters, rebuild e-books |
| `make_ebook` | Build epub, txt, json; pdf, mobi, azw3 and others need Calibre on the server |
| `save_ebook` | Copy an e-book file to a local directory |
| `get_job`, `cancel_job` | Poll or stop a job |

Tools that start a job wait `wait_seconds` (default 60). A slow job returns `finished: false`; poll it with `get_job`.

## Limits

- The server runs one job queue: an all-source search delays every job queued behind it. Pass `domain` to `search_novels`, or `cancel_job` it.
- Chapter content is the server's HTML.

## Development

```bash
uv sync --extra dev
uv run pytest
```

Personal use only: sites publish fiction under their own terms.
