# OneNote Agent - Design Document

**Date:** 2026-03-27
**Status:** Approved
**Author:** Harv Balu + Claude

## Goal

Build a system that mirrors all OneNote content to the VPS, keeps it in sync, and makes it queryable from any device (Mac, mobile, web) via Claude Code MCP tools and a REST API.

## Architecture Overview

**Approach B: n8n scans, dedicated server serves.**

```
Hostinger VPS (85.31.234.11)
  ├── n8n (existing) - Scanner workflow
  │     - 5AM cron + webhook trigger
  │     - Graph API scan, HTML→markdown
  │     - Email summary, OneDrive upload
  │     - Writes to /onenote-mirror/ (shared volume)
  │
  ├── onenote-server (new Docker container)
  │     - FastAPI REST API (:8100)
  │     - MCP Server (SSE)
  │     - SQLite FTS5 search index
  │     - Reads from /onenote-mirror/
  │
  └── Traefik (existing) - reverse proxy
        - onenote.srv1012057.hstgr.cloud → :8100
```

**Data flows:**
- n8n → VPS filesystem (`/onenote-mirror/`)
- n8n → OneDrive (auto-syncs to Mac)
- n8n → Email summary to HarvRealtor@outlook.com
- onenote-server → Claude (any device) via MCP or REST

## OneNote Inventory

- 17 notebooks, 73 sections, ~200-400 pages
- Estimated storage: <50 MB as markdown (VPS has 71 GB free)
- Key notebooks: Clients, Computers, Home, Mint, Realty Experts, Websites-RealEstate

## Component 1: n8n Scanner Workflow

**Triggers:**
- Schedule: 5 AM Pacific daily
- Webhook: POST for on-demand sync

**Flow:**
1. Load `_manifest.json` (previous scan state: `{pageId: lastModifiedDateTime}`)
2. Graph API: list all notebooks → sections → pages with `lastModifiedDateTime`
3. Compare against manifest → identify new/changed/deleted pages
4. Download changed pages: `GET /me/onenote/pages/{id}/content`
5. Convert HTML to clean markdown with YAML frontmatter
6. Write to `/onenote-mirror/{Notebook}/{Section}/{PageTitle}.md`
7. Update `_manifest.json` and append to `_changelog.md`
8. Upload changed files to OneDrive (`/OneNote-Mirror/`) via Graph API
9. Send email summary to HarvRealtor@outlook.com via Graph API
10. Return changelog (webhook response)

**File structure:**
```
/onenote-mirror/
├── _manifest.json
├── _changelog.md
├── Ancient Knowledge/
│   ├── Astrology/
│   ├── Food/
│   └── ...
├── Clients/
│   ├── 2471-Almaden-Ct/
│   └── 204-Daylily-Ln/
├── Computers/
│   ├── Claude/
│   └── n8n/
├── Home/
│   └── Insurance/
└── ... (17 notebooks, 73 sections)
```

**Markdown file format:**
```markdown
---
id: "0-7F2B39559A0F2CE9!s..."
title: "Car Insurance - Progressive"
notebook: "Home"
section: "Insurance"
modified: "2026-03-25T18:30:00Z"
---

[page content converted from HTML to markdown]
```

**OAuth:** Renew client secret on existing Azure app (`c96fe600-e76c-4605-850f-8e40e822d526`, `n8n-HarvRealtor-Outlook-com`). n8n's built-in Microsoft OAuth credential handles token refresh automatically.

## Component 2: onenote-server

**Stack:** Python 3.12, FastAPI, SQLite FTS5, uvicorn
**Docker image:** ~50MB (python:3.12-slim)
**Port:** 8100 (internal), HTTPS via Traefik

### REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/search?q=flood+insurance` | Full-text search, ranked results with snippets |
| GET | `/read/{notebook}/{section}/{page}` | Full page content |
| GET | `/list` | All notebooks/sections/pages with modified dates |
| GET | `/list/{notebook}` | Sections and pages in a notebook |
| GET | `/changelog` | Recent changes |
| GET | `/changelog?since=2026-03-26` | Changes since date |
| GET | `/health` | Health check + last scan time |
| POST | `/reindex` | Force rebuild search index |

### MCP Tools

| Tool | Description |
|---|---|
| `onenote_search` | Full-text search across all notes |
| `onenote_read` | Read a specific page's full content |
| `onenote_list` | List notebooks, sections, or pages |
| `onenote_changelog` | What changed recently |

### Search

- SQLite FTS5 for fast full-text search with BM25 ranking
- Indexes: page title, content, notebook name, section name
- Returns: title, path, relevance score, content snippet

### Startup behavior

1. Scan `/onenote-mirror/` directory
2. Build/rebuild SQLite FTS5 index
3. Watch for file changes → auto-reindex when n8n writes new files

### Auth

- API key in `X-API-Key` header (stored in `.env.secrets`)
- Single key, sufficient for single-user system

## Component 3: Infrastructure

### Docker Compose addition

New service `onenote-server` added to existing VPS docker-compose. Shared volume `onenote-mirror` mounted in both n8n and onenote-server containers.

### Traefik routing

- `onenote.srv1012057.hstgr.cloud` → onenote-server:8100
- TLS via Let's Encrypt (Traefik handles this automatically)

### Claude Code MCP config (`~/.claude/mcp.json`)

```json
"onenote": {
  "type": "sse",
  "url": "https://onenote.srv1012057.hstgr.cloud/mcp/sse",
  "headers": {
    "X-API-Key": "{{from .env.secrets}}"
  }
}
```

## Component 4: Skills

### `/sync-onenote` (global skill)
- Calls n8n webhook URL (HTTPS POST)
- Displays changelog results
- Available from any workspace

### `/onenote [question]` (global skill, optional)
- Calls `onenote_search` + `onenote_read` MCP tools
- Nice shortcut but not strictly needed (Claude uses MCP tools automatically)

### Local fallback (Mac only)
Claude Code on Mac can also read directly from:
`~/Library/CloudStorage/OneDrive-Personal/OneNote-Mirror/`
Faster than API, works if VPS is down.

## Security

| Concern | Solution |
|---|---|
| API exposed to internet | API key on all requests |
| API key storage | `.env.secrets` (never in code/memory) |
| OAuth tokens on VPS | n8n encrypted credentials |
| HTTPS | Traefik TLS (already configured) |
| Content on VPS disk | Single-user VPS, same security as n8n |

## Build Order

| Step | What | Effort |
|---|---|---|
| 1 | Renew Azure app client secret | 5 min (Harv, browser) |
| 2 | Update n8n Microsoft OAuth credential | 5 min |
| 3 | Build n8n scanner workflow | Medium |
| 4 | Build onenote-server (FastAPI + MCP + SQLite FTS) | Medium (~300 lines) |
| 5 | Docker Compose + Traefik config on VPS | Small |
| 6 | Create global `/sync-onenote` skill | Small |
| 7 | Add remote MCP to `~/.claude/mcp.json` | 2 min |
| 8 | Test end-to-end | Small |

## Decisions Made

- **Approach B** over A (n8n-only) and C (all-in-one): Clean separation, proper search via SQLite FTS
- **n8n for scanning** over Python script: Handles OAuth automatically, already runs 24/7, built-in scheduling/email
- **Renew existing Azure app secret** over creating new app: Simpler
- **OneDrive as Mac sync bridge**: Zero extra infrastructure, auto-sync
- **API key auth** over OAuth for the server: Single user, HTTPS, sufficient
- **Global skills**: Available from any workspace
- **Email + changelog** for notifications: Both passive and active awareness
