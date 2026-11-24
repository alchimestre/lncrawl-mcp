# lncrawl-mcp

Let an AI assistant search web-novel sites, download chapters, read them, and export EPUBs through [Lightnovel Crawler](https://github.com/lncrawl/lightnovel-crawler) (`lncrawl`). It is an [MCP](https://modelcontextprotocol.io) server that calls the REST API of a running `lncrawl server`.

> "Find *Solo Leveling* on a French source, download the first 10 chapters, read me chapter 1, then build an EPUB."

Status: early (0.1). Python 3.10+, tested against lncrawl 4.14.0. Not affiliated with lncrawl.

## Quick start

1. Install [uv](https://docs.astral.sh/uv/) and lncrawl (`pipx install lightnovel-crawler`).
2. Start the server, bound to localhost:

   ```bash
   lncrawl server --host 127.0.0.1 --port 8181
   ```

   The default bind is `0.0.0.0`, and a fresh server accepts `admin` / `admin`. Change the password in the web UI at `http://127.0.0.1:8181` before exposing the port.
3. Install this server:

   ```bash
   uv tool install git+https://github.com/alchimestre/lncrawl-mcp
   ```

4. Add it to your MCP client:

   ```json
   {
     "mcpServers": {
       "lncrawl": {
         "command": "lncrawl-mcp",
         "env": {
           "LNCRAWL_EMAIL": "admin",
           "LNCRAWL_PASSWORD": "your-password"
         }
       }
     }
   }
   ```

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `LNCRAWL_URL` | `http://127.0.0.1:8181` | Server base URL |
| `LNCRAWL_EMAIL`, `LNCRAWL_PASSWORD` | none | Login; renewed when the token expires |
| `LNCRAWL_TOKEN` | none | API token, used instead of a login |
| `LNCRAWL_DOWNLOAD_DIR` | `./downloads` | Where `save_ebook` writes |

## Tools

| Tool | Does |
|------|------|
| `list_sources` | Supported sites, filtered by domain, language, search support |
| `search_novels` | Title search across all sources, or one `domain` |
| `add_novel` | Fetch metadata and chapter list from a novel URL |
| `list_novels`, `get_novel`, `list_chapters` | Browse the server's library |
| `read_chapter` | Chapter text, downloaded first when missing |
| `download_missing_chapters` | Download every undownloaded chapter |
| `update_novel` | Refresh metadata, download new chapters, rebuild e-books |
| `make_ebook` | Build `epub`, `txt`, `json`; `pdf`, `mobi`, `azw3` and others need Calibre on the server |
| `save_ebook` | Copy an e-book file to a local directory |
| `get_job`, `cancel_job` | Poll or stop a job |

Tools that start a job wait `wait_seconds` (default 60). A slower job returns `finished: false`; poll it with `get_job`.

## Limits

- lncrawl runs one job queue. An all-source search delays every job behind it: pass `domain` to `search_novels`, or `cancel_job` it.
- `read_chapter` returns the server's HTML, not plain text.
- Not covered: translation, libraries, read history, admin endpoints. Use the lncrawl web UI.
- Whether you may download a novel depends on the source site's terms.

## Development

```bash
uv sync --extra dev
uv run pytest
```
