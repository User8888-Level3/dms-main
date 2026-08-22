# HARV BALU — Photo Portfolio Site · Build Contract (SPEC)

**Read this whole file before writing any code. Every agent implements EXACTLY this contract.**

A private-first photography portfolio inspired by gregorcollienne.com (typographic, minimal,
clean, editorial). Photos live on the Synology NAS share mounted at `/Volumes/photo` and are
NEVER copied off it (derivatives live in a hidden folder on the same share). A small
self-contained Python app (stdlib server + SQLite) provides:

1. **Public site** — scattered-collage landing with giant "HARV BALU" type, work/collection
   pages, lightbox. Only `visibility='public'` photos ever appear.
2. **Admin panel** — browse EVERYTHING (private included), toggle public/private per photo or
   per folder, mark artwork, mint share links with expiry, revoke links.
3. **Share links** — `/s/<token>` shows one photo to a friend. Optional expiry (24h / 7d /
   30d / custom / never). Expired/revoked → elegant "link expired" page. Private photos are
   reachable ONLY through a valid token.

**Default = private.** Seed rule marks a curated art subset public on first index only.

---

## File layout (all paths absolute)

```
/Users/harvinderbalu1/Library/CloudStorage/GoogleDrive-harvinder.balu@gmail.com/My Drive/ClaudeCode/Photography/portfolio/
  SPEC.md                    ← this file
  portfolio_app/
    __init__.py              ← empty
    config.py                ← Agent A
    db.py                    ← Agent A
    indexer.py               ← Agent A
    retry.py                 ← Agent A (copy pattern from ../photo_index/retry.py)
    server.py                ← Agent B
    render.py                ← Agent B (template loader, string.Template based)
  templates/
    index.html               ← Agent C (landing)
    work.html                ← Agent C (collections grid)
    collection.html          ← Agent C (one collection)
    share.html               ← Agent C (share-link page)
    expired.html             ← Agent C (dead-link page)
    admin.html               ← Agent D
  static/
    style.css                ← Agent C (public design system; admin may extend)
    app.js                   ← Agent C (parallax, lightbox)
    admin.css                ← Agent D
    admin.js                 ← Agent D
  data/                      ← runtime (DB lives here; gitignored; mkdir at runtime)
```

Python: `../.venv/bin/python` (3.13; has Pillow, pillow_heif, imagehash). Server + db are
**stdlib-only**. Indexer may use Pillow/pillow_heif and shell out to `ffmpeg` (installed).

## config.py (Agent A) — exact names

```python
ROOT          = Path(<portfolio dir above>)
PHOTO_MOUNT   = Path("/Volumes/photo")
DERIV_ROOT    = PHOTO_MOUNT / ".portfolio"          # thumbs+display live ON the NAS share
THUMB_DIR     = DERIV_ROOT / "thumb"                # <sha1[:2]>/<sha1>.jpg  (400px, q82)
DISPLAY_DIR   = DERIV_ROOT / "display"              # <sha1[:2]>/<sha1>.jpg  (1600px, q85)
DB_PATH       = ROOT / "data" / "portfolio.db"
HOST, PORT    = "127.0.0.1", 8770
BASE_URL      = "http://127.0.0.1:8770"             # share links composed from this
ADMIN_TOKEN   = None    # future public hosting; None + localhost ⇒ admin allowed
ALLOW_LOCALHOST_ADMIN = True
SITE_NAME     = "HARV BALU"
CONTACT_EMAIL = "homes@HarvRealtor.com"
INSTAGRAM_URL = "https://www.instagram.com/harvrealtor/"
EXCLUDE_DIRS  = {"#recycle", "@eaDir", ".portfolio"}   # plus any name starting with "."
IMAGE_EXTS    = {".jpg",".jpeg",".png",".heic",".tif",".tiff"}
VIDEO_EXTS    = {".mp4",".mov",".avi"}
PUBLIC_SEED_FOLDERS = {"AI Generated","Cosmology","Half Moon Bay","Cancún","Niagara Falls",
  "Monterey Bay Aquarium","Alviso Marina County Park","Ed R. Levin County Park","New York City"}
ARTWORK_SEED_FOLDERS = {"AI Generated","Cosmology"}
THUMB_EDGE, THUMB_Q   = 400, 82
DISPLAY_EDGE, DISPLAY_Q = 1600, 85
WORKERS = 8
```

⚠️ **Unicode:** macOS SMB reports names in NFD ("Cancún" decomposed). ALWAYS
`unicodedata.normalize("NFC", name)` before comparing folder names to the seed sets and
before storing `folder` in the DB.

## db.py (Agent A) — schema + API

SQLite, WAL mode, `check_same_thread=False`, one module-level `connect()` returning a new
connection (server threads each open their own).

```sql
CREATE TABLE IF NOT EXISTS photos(
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,          -- absolute original path on /Volumes/photo (NFC)
  folder TEXT NOT NULL,               -- top-level collection name (NFC)
  filename TEXT NOT NULL,
  sha1 TEXT NOT NULL,
  ext TEXT NOT NULL,                  -- lowercase, with dot
  kind TEXT NOT NULL,                 -- 'image' | 'video'
  width INTEGER, height INTEGER,
  bytes INTEGER, mtime REAL,
  taken_at TEXT,                      -- ISO8601 or NULL (EXIF DateTimeOriginal; else mtime)
  visibility TEXT NOT NULL DEFAULT 'private',   -- 'private' | 'public'
  is_artwork INTEGER NOT NULL DEFAULT 0,
  indexed_at TEXT NOT NULL,
  missing INTEGER NOT NULL DEFAULT 0  -- file vanished on re-index
);
CREATE INDEX IF NOT EXISTS idx_photos_folder ON photos(folder);
CREATE INDEX IF NOT EXISTS idx_photos_vis ON photos(visibility);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_sha1 ON photos(sha1);
CREATE TABLE IF NOT EXISTS shares(
  token TEXT PRIMARY KEY,             -- secrets.token_urlsafe(16)
  photo_id INTEGER NOT NULL REFERENCES photos(id),
  created_at TEXT NOT NULL,
  expires_at TEXT,                    -- ISO8601 UTC or NULL = never
  revoked INTEGER NOT NULL DEFAULT 0,
  note TEXT
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
```

Sha1 collision across distinct paths (same file copied twice in the share): keep FIRST row,
skip subsequent duplicates (log them). `idx_photos_sha1` enforces.

Provide helper functions (used by server + indexer): `get_photo_by_sha1`, `get_photo`,
`public_photos(folder=None)`, `all_folders()` → `[{folder, total, public, cover_sha1}]`
(cover = newest public photo, else newest photo), `set_visibility(ids|folder, vis)`,
`set_artwork(ids, flag)`, `create_share(photo_id, expires_at, note)`,
`get_share(token)`, `revoke_share(token)`, `list_shares()` (join photo thumb info),
`share_valid(row) -> bool` (not revoked and (expires_at is NULL or expires_at > now UTC)).
Timestamps: `datetime.now(timezone.utc).isoformat(timespec="seconds")`.

## indexer.py (Agent A)

CLI: `python -m portfolio_app.indexer [--limit N] [--folder NAME] [--workers N] [--reseed]`

- Walk `PHOTO_MOUNT` one level of top folders (skip EXCLUDE_DIRS and dot-names), recurse
  inside; `folder` = NFC top-level dir name. Skip files: hidden, `Thumbs.db`, `desktop.ini`,
  wrong ext, 0 bytes.
- Incremental: skip when DB row exists with same `(mtime, bytes)` AND both derivative files
  exist. Otherwise (re)process: sha1 full file; EXIF `DateTimeOriginal` via
  `PIL.Image.getexif()` tag 36867 → ISO (fallback file mtime); write thumb 400/q82 +
  display 1600/q85 (progressive, optimize, `ImageOps.exif_transpose`, RGB convert; pattern =
  `../photo_index/thumbs.py`). Videos: ffmpeg frame at t=1s (retry t=0) → same two JPEGs.
  HEIC via `pillow_heif.register_heif_opener()`.
- **Seed visibility ONLY on first insert:** folder ∈ PUBLIC_SEED_FOLDERS → 'public';
  folder ∈ ARTWORK_SEED_FOLDERS → is_artwork=1. NEVER change visibility/is_artwork on
  re-index of an existing row (manual admin choices are sacred). Mark DB rows `missing=1`
  when file gone (never delete rows — shares may reference them).
- ThreadPoolExecutor(WORKERS) for hashing+derivatives, single main-thread DB writes
  (executor returns results, main loop commits every 50). Progress line per 25 files:
  `"[137/3805] Family/IMG_2041.jpg ok"` + final summary. Copy `@smb_retry()` decorator
  pattern from `../photo_index/retry.py` for all NAS reads.

## render.py (Agent B)

`render(template_name, **ctx) -> str`: read `templates/<name>`, `string.Template(...)
.safe_substitute(ctx)`. (`$var` placeholders in templates; CSS/JS braces stay untouched.
Literal `$` in templates must be `$$`.) Also `html_escape` re-export.

## server.py (Agent B) — stdlib ThreadingHTTPServer, port 8770

Follow the style of `../photo_server.py` (Handler class, `_respond_json`, cache headers,
`log_message` to stderr). Bind 127.0.0.1.

**Admin gate** `is_admin(handler) -> bool`: client ip == 127.0.0.1 and
ALLOW_LOCALHOST_ADMIN → True; else cookie `adm` == ADMIN_TOKEN (when set). All `/admin*` and
`/api/admin/*` routes 403 otherwise.

**Routes (GET):**
- `/` → `index.html` — ctx: `hero_name`, `collage_tiles` (server-built HTML for up to 14
  public photos: newest artwork first, then other public; each tile
  `<figure class="tile tile--N" data-speed="0.xx"><img src="/media/thumb/<sha1>.jpg" ...></figure>`),
  `about_html`, contact/instagram vars, `year`.
- `/work` → `work.html` — public collections: cards with cover display img, name, count.
- `/c/<folder>` → `collection.html` — public photos of that folder (404 if none), grid of
  thumbs, lightbox uses display size. URL-encode/decode folder names (NFC).
- `/s/<token>` → share flow: unknown token → 404 `expired.html`; revoked/expired → 410
  `expired.html`; valid → `share.html` ctx: display img URL **with `?t=<token>`**, filename,
  taken date, expiry line ("Link expires <local date>" / "Permanent link"), download link
  `/media/orig/<sha1>?t=<token>`.
- `/media/<kind>/<sha1>[.jpg]` where kind ∈ {thumb, display, orig} → **THE security
  chokepoint**:
  1. Look up photo by sha1 (+ not missing) else 404.
  2. If `visibility != 'public'`: require `?t=` token whose share row → this photo_id and
     `share_valid` → else 403. Admin (is_admin) always allowed.
  3. thumb/display: serve JPEG from THUMB_DIR/DISPLAY_DIR (`<sha1[:2]>/<sha1>.jpg`).
     orig: serve `photos.path` with correct Content-Type (mimetypes),
     `Content-Disposition: attachment; filename="<filename>"`.
  4. sha1 must match `^[0-9a-f]{40}$` (reject anything else — no path input from client
     ever touches the filesystem).
  5. Cache-Control: public photos thumb/display `public, max-age=31536000, immutable`
     (sha1-addressed); private/orig → `private, no-store`.
  Stream in 64 KB chunks; support HEAD.
- `/admin` → `admin.html` (gate first).
- `/healthz` → `{"ok": true, "photos": N}`.
- Static: `/static/*` from `static/` (safe path join, no `..`), Cache-Control `no-cache`.
- HTML responses: `Cache-Control: no-cache`.

**Routes (JSON; POST unless noted) — admin-gated:**
- GET `/api/admin/state` → `{folders:[{folder,total,public,artwork,cover_sha1}], shares:N}`
- GET `/api/admin/photos?folder=X` → `{photos:[{id,sha1,filename,kind,visibility,is_artwork,taken_at,width,height}]}` ordered taken_at
- POST `/api/admin/visibility` `{ids:[...]| folder:"X", visibility:"public"|"private"}` → `{ok,changed:N}`
- POST `/api/admin/artwork` `{ids:[...], artwork:true|false}`
- POST `/api/admin/share` `{photo_id, expires:"24h"|"7d"|"30d"|"never"|"YYYY-MM-DD", note?}`
  → `{ok, url: BASE_URL+"/s/"+token, token, expires_at}` (custom date = end of that day UTC)
- POST `/api/admin/revoke` `{token}` → `{ok}`
- GET `/api/admin/shares` → `{shares:[{token,url,photo_id,sha1,filename,created_at,expires_at,revoked,expired,note}]}`
- 404/400/403 JSON errors `{error: "..."}`. Body limit 64 KB. All inputs validated.

## Design system (Agents C & D) — "Editorial Cream" (Gregor Collienne homage)

Tokens (CSS custom props in style.css `:root`):
```
--paper:#F2EFE9;  --ink:#0B0B0A;  --ink-soft:#57544E;  --line:#DDD8CE;
--font-display:'Anton', 'Arial Narrow', sans-serif;      /* giant condensed caps */
--font-body:'Instrument Sans', system-ui, sans-serif;
--font-mono:'Geist Mono', ui-monospace, monospace;       /* tiny labels/EXIF */
```
Google Fonts `<link>`: Anton + Instrument Sans (400/500/600) + Geist Mono (400/500).
Flat editorial: **no border-radius, no drop shadows** on photos. Hover = subtle
`scale(1.015)` + slight brightness. Motion respects `prefers-reduced-motion`.

**index.html** — full-viewport cream page; small `+` glyph top-center (mono font);
absolutely-positioned scattered collage of ~10–14 tiles hugging the edges (mix of portrait/
landscape sizes; some bleed off-viewport edges exactly like the reference); centered
`<h1 class="hero">HARV BALU</h1>` (Anton, `clamp(3.5rem, 11vw, 10rem)`, tight tracking,
uppercase) sitting ABOVE tiles in z-order but NOT obscured (tiles avoid the center band).
Tiles get gentle scroll/mouse parallax via `data-speed` (app.js). Page scrolls ~200vh;
second screen = short intro line + `WORK →` link. Minimal fixed nav top-right:
`WORK` `ABOUT` (mono, small, uppercase). ABOUT opens the overlay (in-page `<dialog>` or
fixed div): cream panel, big Anton headings `OVERVIEW` / `WORK`, an all-caps bold paragraph
(placeholder bio: Bay Area photographer — landscapes, wildlife, cosmology, travel, AI art),
`CONTACT ME` mailto bottom-left, `IN` instagram bottom-right, `×` close.
Provide `$collage_tiles`, `$hero_name`, `$about_html`, `$contact_email`, `$instagram_url`,
`$year` template slots.

**work.html** — header `WORK` (Anton, huge). Grid of collection cards (`$collection_cards`):
cover image (display size, `aspect-ratio: 4/3`, object-fit cover), below it mono caption
`01 — COSMOLOGY · 162` style (index number, name, count). Click → `/c/<folder>`.

**collection.html** — header = folder name (Anton) + count + `← WORK` back link. Masonry via
CSS columns (`columns: 4` desktop → 2 tablet → 1 phone) of thumbs (`$photo_tiles`,
`loading="lazy"`). Click → lightbox (app.js): fixed overlay `rgba(11,11,10,.96)`, display
image centered, filename + date caption (mono), ‹ › arrows + keyboard nav + Esc, `×`.
Video tiles: `▶` badge (mono), lightbox shows poster + "download to play" note.

**share.html** — standalone minimal: small `HARV BALU` wordmark top-center (Anton, ~1.2rem),
photo centered (max 82vh, display+token URL), caption row: `$filename` · `$taken_line`, then
`$expiry_line` (mono, ink-soft), `DOWNLOAD ORIGINAL` underlined mono link (`$download_url`).
Footer `© $year Harv Balu`. **expired.html**: giant Anton `LINK EXPIRED`, line "Ask Harv for
a fresh one.", wordmark. (Also used for unknown token — same body, server sets 404/410.)

**app.js** — (1) parallax: on scroll + subtle mousemove, translate tiles by
`data-speed`; disable when `prefers-reduced-motion`. (2) entrance: tiles fade/rise once via
IntersectionObserver. (3) lightbox for collection pages: builds from
`<a class="ph" data-sha1 data-filename data-taken data-kind href="/media/display/...">`
anchors. (4) ABOUT overlay open/close. No frameworks, no build step, ES2020.

**admin.html + admin.css + admin.js (Agent D)** — same cream tokens but denser, data-tool
feel (import style.css then admin.css). Layout: left sidebar = folder list (name, `pub/total`
counts, artwork star for seed-art folders) + "All" + "Shares" views; main = toolbar + grid.
Toolbar: folder name, `Select all / none`, bulk `Make Public` `Make Private` `Artwork ✦`
`Share…` buttons (act on checked tiles), search-by-filename filter (client-side). Grid tiles:
thumb + checkbox + badge `PUBLIC` (ink chip) / `PRIVATE` (outlined chip + lock glyph) +
`✦` when artwork; click thumb toggles check; alt-click opens `/media/display/<sha1>.jpg`.
Share dialog (native `<dialog>`): radio 24 hours / 7 days / 30 days / Never expires /
Custom date (`<input type=date>`), optional note, `Create link` → shows URL in a readonly
input + `Copy` button (navigator.clipboard). Per-tile hover `⤴ Share` shortcut too.
Shares view: table (thumb, filename, created, expires, status chip ACTIVE/EXPIRED/REVOKED,
Copy, Revoke). All via the JSON API; optimistic UI updates; errors → small toast.
`PRIVATE` must read as clearly locked; accent for destructive Revoke = `#B3261E`.

## Hard rules (every agent)

- ⚠️ NEVER pair `background-attachment: fixed` with a blurred sticky header (macOS Chrome
  compositor black-screen). Avoid `backdrop-filter` on sticky elements entirely.
- No symlinks anywhere (Google Drive destroys them). No external JS/CSS except Google Fonts.
- Only stdlib in server/db/render; Pillow/pillow_heif/ffmpeg only in indexer.
- All user-visible strings escaped with `html.escape` when interpolated server-side.
- Filesystem access from client input: ONLY via sha1 regex + DB lookup. No client paths.
- Python style: match `../photo_server.py` / `../photo_index/*` (type hints, docstrings,
  section comment rules).
