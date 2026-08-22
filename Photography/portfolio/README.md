# HARV BALU — Photo Portfolio

A private-first photography portfolio, styled after [gregorcollienne.com](https://gregorcollienne.com)
(cream, giant condensed type, scattered-collage landing). Your photos **never leave the
Synology** — the app reads originals from the `/Volumes/photo` share and writes only
thumbnails back to a hidden `.portfolio/` folder on that same share. Everything runs
locally on your Mac.

It gives you three things you asked for:

1. **A public portfolio** — only photos you mark **Public** ever appear on the site.
2. **Lock-down by default** — every photo starts **Private**. Private photos are invisible
   on the public site and cannot be opened by anyone without a share link.
3. **Share links with expiry** — click a photo → get a link for a friend, set to expire in
   24h / 7 days / 30 days / a custom date, or **never** (for artwork you want up forever).
   Expired or revoked links show an "expired" page. Revoke any link instantly.

---

## Run it

**Double-click `Portfolio.command`** (in this folder). It starts the local server and opens
the browser. Close the Terminal window to stop it.

- Public site: <http://127.0.0.1:8770/>
- Admin panel: <http://127.0.0.1:8770/admin>

First launch needs the `/Volumes/photo` share mounted (Finder → Go → Connect to Server →
`smb://172.22.2.147/photo`). First time you open a `.command`, macOS Gatekeeper may need
right-click → Open.

## Add or refresh photos

**Double-click `Reindex-Photos.command`.** It scans the share and adds anything new. It's
incremental (skips already-indexed files) and **never changes your Public/Private/Artwork
choices** — those are yours forever. Originals are only ever read.

---

## Using the admin panel

- **Left sidebar** — every collection with a `public/total` count; **All**; **Shares**.
- **Select** photos (click a tile, or *Select all*), then:
  - **Make Public** / **Make Private** — per selection, or the whole folder when nothing is
    selected.
  - **Artwork ✦** — flags your best work; artwork shows first in the landing collage.
  - **Share…** — mint a link for one selected photo (pick an expiry + optional note).
- **Shares** view — every link you've made: status (Active / Expired / Revoked), **Copy**,
  **Revoke**.

**Make a photo public-forever ("artwork"):** select it → Make Public → Artwork ✦.
**Share one privately for a week:** select it → Share… → *7 days* → Copy → send.

---

## How the privacy works (why it's safe)

Every image request goes through one checkpoint (`/media/<kind>/<sha1>`):

- **Public** photo → served to anyone.
- **Private** photo → served **only** to you (the admin, on this Mac) **or** to a request
  carrying a valid, unexpired, non-revoked share token that was minted **for that exact
  photo**. A token for photo A cannot open photo B. No token → **403**.
- Filenames/paths from the browser never touch the disk — lookups are by a 40-char hash only.
- Share/private images are sent `no-store` so browsers and proxies don't cache them.

This was tested end-to-end: public open, private blocked, valid token opens, **expired token
blocked**, cross-photo token blocked, admin API blocked for non-admins, path-traversal blocked.

---

## ⚠️ Hosting it publicly

Locally (just double-clicking `Portfolio.command`) the admin panel trusts `127.0.0.1` —
that's you, on this Mac. Safe.

For a public deployment the app has built-in switches (no code edits) — start it with:

```bash
PORTFOLIO_PUBLIC=1 \
PORTFOLIO_ADMIN_TOKEN="<long random secret>" \
PORTFOLIO_BASE_URL="https://your.domain" \
python -m portfolio_app.server
```

What that does (all verified by test):

- `PORTFOLIO_PUBLIC=1` — localhost is **no longer trusted** as admin (reverse proxies
  connect from localhost; trusting it would hand every visitor the admin panel).
- `PORTFOLIO_ADMIN_TOKEN` — enables **/admin/login**: you sign in once with the token,
  it sets an HttpOnly cookie for 30 days. Wrong-token attempts are throttled
  (10 per 10 minutes per IP). `/admin/logout` signs out.
- `PORTFOLIO_BASE_URL` — share links are composed from the real public URL.
- All responses send `Referrer-Policy: same-origin` so share-link tokens never leak
  through outbound requests.
- Also available: `PORTFOLIO_HOST` / `PORTFOLIO_PORT`.

Still required at the proxy layer: **HTTPS** (tokens travel inside share URLs).
Tell me the hosting home (Synology Web Station reverse-proxy or the n8n VPS both work)
and I'll wire up the deployment.

---

## Layout

```
portfolio/
  Portfolio.command        double-click → run the local server
  Reindex-Photos.command   double-click → scan the share for new photos
  portfolio_app/           config, db, indexer, server, render  (stdlib server; Pillow only in indexer)
  templates/               index, work, collection, share, expired, admin  ($var slots)
  static/                  style.css, app.js, admin.css, admin.js
  data/                    local catalog DB (gitignored — rebuildable by re-indexing)
  SPEC.md                  the build contract
```

Photos + thumbnails live on the NAS (`/Volumes/photo` and `/Volumes/photo/.portfolio`),
never in this folder or in git.
