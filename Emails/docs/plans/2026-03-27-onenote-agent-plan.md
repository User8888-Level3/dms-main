# OneNote Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mirror all OneNote content to VPS as searchable markdown, queryable from any device via MCP and REST API.

**Architecture:** n8n workflow scans OneNote via Graph API on a 5AM schedule (or on-demand webhook), writes markdown files to a shared Docker volume. A separate FastAPI container indexes those files with SQLite FTS5 and serves them via REST + MCP SSE. Traefik provides HTTPS.

**Tech Stack:** n8n (existing), Python 3.12/FastAPI/SQLite FTS5 (new container), Docker Compose, Traefik (existing)

**VPS:** 85.31.234.11 (SSH: root@85.31.234.11), Docker path: `/docker/n8n/`, n8n URL: `https://n8n.srv1012057.hstgr.cloud`

**Design doc:** `docs/plans/2026-03-27-onenote-agent-design.md`

---

## Task 1: Renew Azure App Client Secret (Harv - Browser)

**This task requires Harv to do manually in the Azure portal.**

**Step 1: Navigate to Azure app**

Go to: https://portal.azure.com → App registrations → `n8n-HarvRealtor-Outlook-com` (Client ID: `c96fe600-e76c-4605-850f-8e40e822d526`)

**Step 2: Create new client secret**

- Click "Certificates & secrets" → "Client secrets" → "New client secret"
- Description: `n8n-onenote-scanner`
- Expiry: 24 months
- Click "Add"
- **COPY THE SECRET VALUE IMMEDIATELY** (it won't be shown again)

**Step 3: Save the secret**

Add to `.env.secrets`:
```
N8N_AZURE_CLIENT_SECRET=<the-secret-value>
```

**Step 4: Verify the app has OneNote permissions**

In the Azure app → API permissions, confirm these delegated permissions exist:
- `Notes.Read`
- `Notes.ReadWrite`
- `Files.ReadWrite` (for OneDrive upload)
- `Mail.Send` (for email summary)
- `User.Read`

If any are missing, click "Add a permission" → Microsoft Graph → Delegated → add them.

**Step 5: Confirm to Claude that the secret is ready**

---

## Task 2: Update n8n Microsoft OAuth Credential

**Step 1: SSH into VPS and note current docker-compose.yml**

```bash
ssh root@85.31.234.11
cat /docker/n8n/docker-compose.yml
```

Save the output — we'll need the exact Traefik labels and volume config for Task 5.

**Step 2: Open n8n credentials UI**

Go to: https://n8n.srv1012057.hstgr.cloud → Settings → Credentials

**Step 3: Find or create Microsoft OAuth2 credential**

- If an existing Microsoft credential exists, edit it
- If not, create new: "Microsoft OAuth2 API" credential type
- Set:
  - Client ID: `c96fe600-e76c-4605-850f-8e40e822d526`
  - Client Secret: `<the secret from Task 1>`
  - Scope: `openid offline_access Notes.Read Notes.ReadWrite Files.ReadWrite Mail.Send User.Read`
  - Auth URI: `https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize`
  - Token URI: `https://login.microsoftonline.com/consumers/oauth2/v2.0/token`

**Step 4: Connect and authorize**

Click "Connect" / "Sign in" → authenticate with HarvRealtor@outlook.com → authorize the app.

**Step 5: Test the credential**

Create a temporary workflow with an HTTP Request node:
- URL: `https://graph.microsoft.com/v1.0/me`
- Authentication: select the Microsoft credential
- Execute → should return user profile JSON

Delete the temp workflow after confirming.

**Step 6: Commit confirmation**

Note the credential name for use in the scanner workflow.

---

## Task 3: Create Shared Docker Volume and Directory Structure

**Step 1: SSH into VPS**

```bash
ssh root@85.31.234.11
```

**Step 2: Create the mirror directory**

```bash
mkdir -p /docker/onenote-mirror
chmod 755 /docker/onenote-mirror
```

**Step 3: Create initial manifest and changelog**

```bash
echo '{}' > /docker/onenote-mirror/_manifest.json
echo '# OneNote Mirror Changelog' > /docker/onenote-mirror/_changelog.md
echo '' >> /docker/onenote-mirror/_changelog.md
```

**Step 4: Verify**

```bash
ls -la /docker/onenote-mirror/
```

Expected: `_manifest.json` and `_changelog.md` present.

---

## Task 4: Build onenote-server (FastAPI + MCP + SQLite FTS)

**Files:**
- Create: `onenote-server/main.py` (FastAPI app + MCP SSE)
- Create: `onenote-server/indexer.py` (SQLite FTS5 index builder)
- Create: `onenote-server/requirements.txt`
- Create: `onenote-server/Dockerfile`
- Test: Manual curl tests after deployment

**Step 1: Create project directory locally**

```bash
mkdir -p /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/onenote-server
```

**Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
mcp[server]==1.0.0
watchdog==4.0.0
pyyaml==6.0.2
```

**Step 3: Write indexer.py**

SQLite FTS5 indexer that:
- Scans `/data/` directory for `.md` files
- Parses YAML frontmatter (id, title, notebook, section, modified)
- Strips frontmatter, indexes content + metadata into FTS5 table
- Provides `search(query)` → ranked results with snippets
- Provides `reindex()` to rebuild from scratch
- Table schema: `pages_fts(title, notebook, section, content, path)`

```python
import sqlite3
import os
import re
from pathlib import Path
from datetime import datetime

DB_PATH = "/data/_index.db"
MIRROR_DIR = "/data"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(title, notebook, section, content, path UNINDEXED, modified UNINDEXED)")
    conn.execute("""CREATE TABLE IF NOT EXISTS pages_meta (
        path TEXT PRIMARY KEY,
        title TEXT,
        notebook TEXT,
        section TEXT,
        modified TEXT,
        onenote_id TEXT
    )""")
    conn.commit()
    conn.close()

def parse_frontmatter(text):
    match = re.match(r'^---\n(.*?)\n---\n(.*)', text, re.DOTALL)
    if not match:
        return {}, text
    import yaml
    meta = yaml.safe_load(match.group(1)) or {}
    content = match.group(2).strip()
    return meta, content

def reindex():
    init_db()
    conn = get_db()
    conn.execute("DELETE FROM pages_fts")
    conn.execute("DELETE FROM pages_meta")

    count = 0
    for md_file in Path(MIRROR_DIR).rglob("*.md"):
        rel = str(md_file.relative_to(MIRROR_DIR))
        if rel.startswith("_"):
            continue

        text = md_file.read_text(encoding="utf-8", errors="replace")
        meta, content = parse_frontmatter(text)

        title = meta.get("title", md_file.stem)
        notebook = meta.get("notebook", "")
        section = meta.get("section", "")
        modified = meta.get("modified", "")
        onenote_id = meta.get("id", "")

        conn.execute("INSERT INTO pages_fts(title, notebook, section, content, path, modified) VALUES (?,?,?,?,?,?)",
                      (title, notebook, section, content, rel, modified))
        conn.execute("INSERT OR REPLACE INTO pages_meta(path, title, notebook, section, modified, onenote_id) VALUES (?,?,?,?,?,?)",
                      (rel, title, notebook, section, modified, onenote_id))
        count += 1

    conn.commit()
    conn.close()
    return count

def search(query, limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, title, notebook, section, modified, snippet(pages_fts, 3, '<b>', '</b>', '...', 40), rank FROM pages_fts WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
        (query, limit)
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "path": row[0],
            "title": row[1],
            "notebook": row[2],
            "section": row[3],
            "modified": row[4],
            "snippet": row[5],
            "score": row[6]
        })
    return results

def list_notebooks():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT notebook, COUNT(*) as pages FROM pages_meta GROUP BY notebook ORDER BY notebook"
    ).fetchall()
    conn.close()
    return [{"notebook": r[0], "pages": r[1]} for r in rows]

def list_pages(notebook=None, section=None):
    conn = get_db()
    query = "SELECT path, title, notebook, section, modified FROM pages_meta"
    params = []
    conditions = []
    if notebook:
        conditions.append("notebook = ?")
        params.append(notebook)
    if section:
        conditions.append("section = ?")
        params.append(section)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY notebook, section, title"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{"path": r[0], "title": r[1], "notebook": r[2], "section": r[3], "modified": r[4]} for r in rows]
```

**Step 4: Write main.py**

FastAPI app with REST endpoints + MCP SSE server:

```python
import os
import json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse
from starlette.routing import Mount

from mcp.server.fastmcp import FastMCP
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import indexer

API_KEY = os.environ.get("ONENOTE_API_KEY", "change-me")
MIRROR_DIR = "/data"

# File watcher to auto-reindex
class MirrorWatcher(FileSystemEventHandler):
    def __init__(self):
        self.last_reindex = datetime.min

    def on_any_event(self, event):
        if event.src_path.endswith(".md") and not os.path.basename(event.src_path).startswith("_"):
            from datetime import timedelta
            now = datetime.now()
            if now - self.last_reindex > timedelta(seconds=30):
                self.last_reindex = now
                indexer.reindex()

@asynccontextmanager
async def lifespan(app):
    count = indexer.reindex()
    print(f"Indexed {count} pages")
    observer = Observer()
    observer.schedule(MirrorWatcher(), MIRROR_DIR, recursive=True)
    observer.start()
    yield
    observer.stop()

# --- FastAPI REST ---
api = FastAPI(lifespan=lifespan)

def check_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")

@api.get("/health")
def health():
    manifest_path = Path(MIRROR_DIR) / "_manifest.json"
    last_scan = "never"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        last_scan = manifest.get("_last_scan", "unknown")
    return {"status": "ok", "last_scan": last_scan, "mirror_dir": MIRROR_DIR}

@api.get("/search")
def api_search(q: str = Query(...), limit: int = Query(20), x_api_key: str = Header(None)):
    check_key(x_api_key)
    return indexer.search(q, limit)

@api.get("/read/{path:path}")
def api_read(path: str, x_api_key: str = Header(None)):
    check_key(x_api_key)
    full_path = Path(MIRROR_DIR) / path
    if not full_path.exists() or not str(full_path).startswith(MIRROR_DIR):
        raise HTTPException(404, "Page not found")
    return {"path": path, "content": full_path.read_text(encoding="utf-8", errors="replace")}

@api.get("/list")
def api_list(notebook: str = Query(None), section: str = Query(None), x_api_key: str = Header(None)):
    check_key(x_api_key)
    if not notebook:
        return indexer.list_notebooks()
    return indexer.list_pages(notebook, section)

@api.get("/changelog")
def api_changelog(since: str = Query(None), x_api_key: str = Header(None)):
    check_key(x_api_key)
    changelog_path = Path(MIRROR_DIR) / "_changelog.md"
    if not changelog_path.exists():
        return {"changelog": "No changelog yet"}
    content = changelog_path.read_text()
    if since:
        lines = content.split("\n")
        filtered = [l for l in lines if l.startswith("#") or l.startswith("##") or since <= l[:10] if len(l) >= 10 and l[0].isdigit()]
        content = "\n".join(filtered) if filtered else "No changes since " + since
    return {"changelog": content}

@api.post("/reindex")
def api_reindex(x_api_key: str = Header(None)):
    check_key(x_api_key)
    count = indexer.reindex()
    return {"status": "ok", "pages_indexed": count}

# --- MCP Server ---
mcp = FastMCP("onenote-server")

@mcp.tool()
def onenote_search(query: str, limit: int = 20) -> str:
    """Search across all OneNote pages. Returns ranked results with snippets."""
    results = indexer.search(query, limit)
    if not results:
        return f"No results found for '{query}'"
    lines = []
    for r in results:
        lines.append(f"**{r['title']}** ({r['notebook']}/{r['section']})")
        lines.append(f"  Modified: {r['modified']}")
        lines.append(f"  {r['snippet']}")
        lines.append(f"  Path: {r['path']}")
        lines.append("")
    return "\n".join(lines)

@mcp.tool()
def onenote_read(path: str) -> str:
    """Read the full content of a OneNote page. Use onenote_search or onenote_list to find the path first."""
    full_path = Path(MIRROR_DIR) / path
    if not full_path.exists():
        return f"Page not found: {path}"
    return full_path.read_text(encoding="utf-8", errors="replace")

@mcp.tool()
def onenote_list(notebook: str = "", section: str = "") -> str:
    """List OneNote notebooks, sections, and pages. Call with no args to list all notebooks. Provide notebook to list its sections/pages. Provide both to filter further."""
    if not notebook:
        notebooks = indexer.list_notebooks()
        return "\n".join(f"- {n['notebook']} ({n['pages']} pages)" for n in notebooks)
    pages = indexer.list_pages(notebook, section or None)
    if not pages:
        return f"No pages found in {notebook}" + (f"/{section}" if section else "")
    lines = []
    current_section = ""
    for p in pages:
        if p["section"] != current_section:
            current_section = p["section"]
            lines.append(f"\n**{current_section}/**")
        lines.append(f"  - {p['title']} (modified: {p['modified'][:10]}) — path: {p['path']}")
    return "\n".join(lines)

@mcp.tool()
def onenote_changelog(since: str = "") -> str:
    """Show what OneNote pages changed recently. Optionally filter by date (YYYY-MM-DD)."""
    changelog_path = Path(MIRROR_DIR) / "_changelog.md"
    if not changelog_path.exists():
        return "No changelog yet. Run a sync first."
    content = changelog_path.read_text()
    if since:
        lines = content.split("\n")
        filtered = []
        include = False
        for l in lines:
            if l.startswith("## ") and len(l) > 5:
                include = l[3:13] >= since
            if include:
                filtered.append(l)
        return "\n".join(filtered) if filtered else f"No changes since {since}"
    return content

# Mount MCP SSE at /mcp
app = FastAPI()
app.mount("/mcp", mcp.sse_app())
app.mount("/", api)
```

**Step 5: Write Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py indexer.py ./

EXPOSE 8100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
```

**Step 6: Test locally (optional)**

```bash
cd onenote-server
# Create a test mirror dir with a sample file
mkdir -p /tmp/test-mirror/Home/Insurance
cat > /tmp/test-mirror/Home/Insurance/Car-Insurance.md << 'TESTEOF'
---
id: "test-123"
title: "Car Insurance - Progressive"
notebook: "Home"
section: "Insurance"
modified: "2026-03-25T18:30:00Z"
---

Progressive auto insurance policy. Policy number: 12345.
Premium: $850/6 months.
TESTEOF

ONENOTE_API_KEY=test-key MIRROR_DIR=/tmp/test-mirror python -c "
import indexer
indexer.MIRROR_DIR = '/tmp/test-mirror'
indexer.DB_PATH = '/tmp/test-mirror/_index.db'
count = indexer.reindex()
print(f'Indexed {count} pages')
results = indexer.search('Progressive')
print(f'Search results: {results}')
"
```

Expected: `Indexed 1 pages` and search results containing "Car Insurance - Progressive".

**Step 7: Commit**

```bash
git add onenote-server/
git commit -m "feat: add onenote-server (FastAPI + MCP + SQLite FTS)"
```

---

## Task 5: Deploy onenote-server to VPS

**Step 1: SSH into VPS and read current docker-compose.yml**

```bash
ssh root@85.31.234.11
cat /docker/n8n/docker-compose.yml
```

**Step 2: Copy onenote-server files to VPS**

```bash
scp -r onenote-server/ root@85.31.234.11:/docker/onenote-server/
```

**Step 3: Generate API key**

```bash
ssh root@85.31.234.11 "openssl rand -hex 32"
```

Save the output — this is the `ONENOTE_API_KEY`.

**Step 4: Add onenote-server to docker-compose.yml**

SSH into VPS and edit `/docker/n8n/docker-compose.yml`. Add this service (adapt Traefik labels to match existing n8n service label format):

```yaml
  onenote-server:
    build: /docker/onenote-server
    container_name: onenote-server
    restart: unless-stopped
    environment:
      - ONENOTE_API_KEY=${ONENOTE_API_KEY}
    volumes:
      - /docker/onenote-mirror:/data
    expose:
      - "8100"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.onenote.rule=Host(`onenote.srv1012057.hstgr.cloud`)"
      - "traefik.http.routers.onenote.entrypoints=websecure"
      - "traefik.http.routers.onenote.tls.certresolver=myresolver"
      - "traefik.http.services.onenote.loadbalancer.server.port=8100"
```

Also add `onenote-mirror` volume mount to the n8n service so the scanner workflow can write to it:

```yaml
  n8n:
    # ... existing config ...
    volumes:
      - n8n_data:/home/node/.n8n  # existing
      - /docker/onenote-mirror:/onenote-mirror  # ADD THIS
```

**Step 5: Add ONENOTE_API_KEY to .env on VPS**

```bash
ssh root@85.31.234.11
echo "ONENOTE_API_KEY=<the-key-from-step-3>" >> /docker/n8n/.env
```

**Step 6: Build and start**

```bash
ssh root@85.31.234.11
cd /docker/n8n
docker compose up -d --build onenote-server
```

**Step 7: Verify**

```bash
# Health check
curl -s https://onenote.srv1012057.hstgr.cloud/health

# Search (should return empty since no pages yet)
curl -s -H "X-API-Key: <key>" https://onenote.srv1012057.hstgr.cloud/search?q=test

# Verify MCP SSE endpoint exists
curl -s https://onenote.srv1012057.hstgr.cloud/mcp/sse -H "X-API-Key: <key>" -N --max-time 3
```

Expected: Health returns `{"status": "ok", ...}`. Search returns `[]`. SSE returns event stream.

**Step 8: Commit any compose changes**

---

## Task 6: Build n8n Scanner Workflow

**Step 1: Create new workflow in n8n**

Go to https://n8n.srv1012057.hstgr.cloud → New workflow → Name: "OneNote Scanner"

**Step 2: Add Schedule Trigger node**

- Type: Schedule Trigger
- Rule: Every day at 5:00 AM
- Timezone: America/Los_Angeles

**Step 3: Add Webhook node (secondary trigger)**

- Type: Webhook
- HTTP Method: POST
- Path: `onenote-scan`
- Authentication: Header Auth (use a webhook secret)
- Response: "Last Node"

**Step 4: Add Code node: "Scan OneNote"**

This is the main scanner logic (~100 lines JS). It:
1. Reads `_manifest.json` from `/onenote-mirror/`
2. Calls Graph API to list all notebooks → sections → pages
3. Compares `lastModifiedDateTime` against manifest
4. Downloads changed pages' HTML content
5. Converts HTML to markdown (strip OneNote XML, convert tags)
6. Writes `.md` files with YAML frontmatter to `/onenote-mirror/{Notebook}/{Section}/`
7. Updates manifest and changelog
8. Returns summary of changes

The Code node uses the Microsoft OAuth2 credential for Graph API calls via `$http` helper.

**Key Graph API calls in sequence:**
```
GET /me/onenote/notebooks?$select=id,displayName&$expand=sections($select=id,displayName)
GET /me/onenote/sections/{sectionId}/pages?$select=id,title,lastModifiedDateTime
GET /me/onenote/pages/{pageId}/content  (only for changed pages)
```

**HTML to markdown conversion:** Strip `<html>`, `<head>`, `<body>` wrappers. Convert `<h1>`-`<h6>` to `#` headings. Convert `<p>` to paragraphs. Convert `<ul>`/`<li>` to `- ` lists. Convert `<table>` to markdown tables. Strip OneNote-specific attributes and data tags. Convert `<img>` to `![](url)` (keep image URLs, don't download).

**Step 5: Add Code node: "Upload to OneDrive"**

For each changed file, upload via Graph API:
```
PUT /me/drive/root:/OneNote-Mirror/{path}:/content
```

Uses the same Microsoft OAuth2 credential.

**Step 6: Add HTTP Request node: "Send Email Summary"**

- Method: POST
- URL: `https://graph.microsoft.com/v1.0/me/sendMail`
- Authentication: Microsoft OAuth2 credential
- Body:
```json
{
  "message": {
    "subject": "OneNote Scan: {{$json.changedCount}} pages updated ({{$now.format('MM/DD')}})",
    "body": {
      "contentType": "HTML",
      "content": "{{$json.changelogHtml}}"
    },
    "toRecipients": [{"emailAddress": {"address": "HarvRealtor@outlook.com"}}]
  }
}
```

**Step 7: Add Respond to Webhook node**

Returns the changelog JSON to the webhook caller.

**Step 8: Connect nodes**

```
Schedule Trigger ──┐
                   ├──► Scan OneNote ──► Upload to OneDrive ──► Send Email ──► Respond to Webhook
Webhook Trigger ───┘
```

**Step 9: Test manually**

Execute the workflow manually in n8n. Verify:
- Markdown files appear in `/docker/onenote-mirror/` on VPS
- `_manifest.json` is populated
- `_changelog.md` has entries
- Email arrives at HarvRealtor@outlook.com
- onenote-server auto-reindexes (check `/health` endpoint for updated page count)

**Step 10: Activate the workflow**

Toggle the workflow to Active.

---

## Task 7: Configure Claude Code MCP Connection

**Step 1: Add API key to .env.secrets**

Add to the local `.env.secrets`:
```
ONENOTE_API_KEY=<the-key-from-task-5-step-3>
N8N_ONENOTE_WEBHOOK_URL=https://n8n.srv1012057.hstgr.cloud/webhook/onenote-scan
N8N_ONENOTE_WEBHOOK_SECRET=<the-webhook-secret-from-task-6>
```

**Step 2: Add remote MCP to `~/.claude/mcp.json`**

```json
"onenote": {
  "type": "sse",
  "url": "https://onenote.srv1012057.hstgr.cloud/mcp/sse",
  "headers": {
    "X-API-Key": "<ONENOTE_API_KEY>"
  }
}
```

**Step 3: Restart Claude Code and verify MCP tools**

Type `/mcp` in Claude Code → verify `onenote` server is connected with 4 tools:
- `onenote_search`
- `onenote_read`
- `onenote_list`
- `onenote_changelog`

**Step 4: Test the tools**

Ask Claude: "Search my OneNote for insurance" → should use `onenote_search` and return results.

---

## Task 8: Create Global `/sync-onenote` Skill

**Files:**
- Create: `~/.claude/skills/sync-onenote/skill.md`

**Step 1: Create skill directory**

```bash
mkdir -p ~/.claude/skills/sync-onenote
```

**Step 2: Write skill.md**

```markdown
---
name: sync-onenote
description: Trigger an immediate OneNote sync scan. Use when user says /sync-onenote, "sync my notes", "update onenote", or "scan onenote now".
---

# Sync OneNote

Trigger an immediate scan of all OneNote notebooks. This calls the n8n webhook to start the scanner workflow.

## Steps

1. Call the n8n webhook to trigger the scan:

\```bash
curl -s -X POST "$N8N_ONENOTE_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $N8N_ONENOTE_WEBHOOK_SECRET"
\```

2. Display the returned changelog to the user

3. If the scan found changes, mention that the MCP search index will auto-update within 30 seconds.
```

**Step 3: Test**

Type `/sync-onenote` in Claude Code → should trigger the scan and show results.

**Step 4: Commit**

```bash
git add ~/.claude/skills/sync-onenote/
git commit -m "feat: add /sync-onenote global skill"
```

---

## Task 9: End-to-End Test

**Step 1: Run full sync**

Type `/sync-onenote` → verify all 17 notebooks are scanned and markdown files created.

**Step 2: Verify OneDrive sync**

Check that files appear at:
```
~/Library/CloudStorage/OneDrive-Personal/OneNote-Mirror/
```

**Step 3: Test search**

Ask Claude: "Search my OneNote for Domii" → verify results from Vendors/Domii section.

**Step 4: Test full page read**

Ask Claude: "Read my Car Insurance - Progressive note" → verify full content returned.

**Step 5: Test changelog**

Ask Claude: "What changed in my OneNote recently?" → verify changelog is returned.

**Step 6: Test email**

Check HarvRealtor@outlook.com for the scan summary email.

**Step 7: Verify 5 AM schedule**

Check the next morning that the scan ran automatically:
- New email summary received
- `_changelog.md` updated
- Any changes reflected in search

**Step 8: Test from mobile (optional)**

Open Claude Code web (claude.ai/code) on phone → ask about a note → verify MCP tools work.

---

## Summary

| Task | Component | Depends On |
|---|---|---|
| 1 | Azure app secret renewal | None (Harv, browser) |
| 2 | n8n OAuth credential | Task 1 |
| 3 | Shared volume on VPS | None |
| 4 | onenote-server code | None |
| 5 | Deploy onenote-server | Tasks 3, 4 |
| 6 | n8n scanner workflow | Tasks 2, 3 |
| 7 | Claude Code MCP config | Task 5 |
| 8 | /sync-onenote skill | Tasks 6, 7 |
| 9 | End-to-end test | All above |

Tasks 1, 3, and 4 can run in parallel. Tasks 5 and 6 can run in parallel after their dependencies.
