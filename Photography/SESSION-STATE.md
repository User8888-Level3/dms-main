# Photography Index — Session State

**Last updated:** 2026-08-21 (THE INSTRUMENT — the /work overture — LIVE)
**Phase:** Feature-complete. Ongoing operations only.

---

## 2026-08-21 — THE INSTRUMENT: a 3D Canon EOS opens /work — commit 904da52 (deploy repo)

**Harv's brief:** make /work "very creative" like the landing: a full-page
hero with a Canon camera that assembles, dismantles, reassembles and
rotates in 3D, showing the mechanics inside "in absolute detail" (the
watch-movement / AirPods-exploded-view genre, refs: awwwards IYO, Apple
AirPods Pro, Ciechanowski's Mechanical Watch); click a button → zoom into
the camera, show the components, then a beautiful picture (sunset/moon);
keep the colour scheme; don't touch the main page. He uses Canon.

**What shipped (live at https://harvbalu.net/work):**
- `static/instrument.js` (~1,290 lines, vanilla, no library): a **painter's-
  algorithm 3D renderer on 2D canvas** + a Canon EOS Rebel-class model
  built in millimetres (EF flange 44 mm: mount z=18, sensor z=−26; 16
  labelled parts incl. 7-blade iris, pentamirror, two-curtain shutter,
  APS-C CMOS, vari-angle LCD). Drawn in the Observatory grammar: ghost
  gold shells, near-void internals, starlight glass with specular glints,
  the sensor in gold. **Scroll-scrubbed runway** (560vh / 480vh mobile,
  sticky stage): assemble (time) → turn → explode+labels → close → swing
  to the front → dolly → **enter the lens as the light** (iris opens,
  mirror lifts, first curtain drops, 9 rays converge) → sensor ignites →
  the photograph scales out of the sensor rect to fill the stage. "Look
  inside" tweens the scroll (~14s); drag turns; readout names each phase.
- Photograph = the **gold moon** `d7bc3b68…` (Cosmology, 2016 · Oct 17),
  `config.INSTRUMENT_PHOTO_SHA1/EPOCH`, bundled into `/img/` by the exporter
  (21 landing-critical images now). Server (`_page_work`) + exporter both
  pass `$instrument_photo` / `$instrument_epoch` (template parity kept).
- New `stage_and_export.py`: exports with the NAS UNMOUNTED — stages
  derivatives from `~/Sites/harv-portfolio/img/` + fetches missing ones
  from the WP host, rebinds `config.THUMB_DIR/DISPLAY_DIR`. **Use this
  instead of `export_static.py` from now on** (the mount is unreliable).
- CSS section "THE INSTRUMENT" appended to `static/style.css`; `.page--meridian`
  padding moved onto `.obs-head`; reduced-motion = unpinned still of the
  exploded view + the moon as a plain plate; no-JS hides the section.
- DESIGN.md: component + layout + motion entries.

**Review workflow (17 agents, 5 lenses + skeptics) confirmed 12, all fixed:**
reduced-motion bitmap measured from the stage (squashed 48%) → measure the
CANVAS rect · label collisions (cross-side, single-pass) → one rect list,
nearest free slot, bounded · drag accepted while masked by the swing and
leaking on scroll-back → input-gated by `S.swing` · Space on the cue
restarted the play (keydown stop, keyup click) → cue click toggles, cue
keys skipped by the stopper, cue blurs on start, Escape/Tab/focusin stop ·
cue focusable while invisible → focusability from painted opacity, blur
when it fades · no idle gate (full redraw at 60–120 fps at rest) → dirty
key in tick(), 0 fps at rest · back/reload mid-runway replayed the
scatter → assembly/chrome are progress-aware (p>.03 = assembled) ·
log/epoch overprint at p .95–1 → sequenced.

**Traps (remember these):**
- ⭐⭐ **A CSS `animation` on opacity OVERRIDES inline `style.opacity`** — the
  chrome entrances had to move into the script (or the cue never faded).
- ⭐⭐ **The in-app browser pane reports `document.hidden=true` and never
  fires IntersectionObserver/rAF for this page** — it cannot verify canvas
  work at all; Playwright (system python3) against localhost:8771 /
  harvbalu.net is the verification path. Hidden-tab gating is also
  redundant (browsers stop rAF themselves) — don't gate on it.
- ⭐ `html { scroll-behavior: smooth }` makes `scrollTo(0, y)` animate — tests
  must use `behavior:'instant'`; the autoplay forces `scrollBehavior=auto`.
- ⭐ The starfield twinkles → md5 screenshot compares are useless; use a
  thresholded pixel diff (or hide `.stars`) when asserting "no change".
- Painter's sort + translucent fills: lathe profiles must be traced CCW in
  the (r,z) half-plane for outward normals; glass is double-sided.
- Launch config `portfolio-static` (port 8771, Photography/.claude) serves dist.

**Open:** source changes live in the Drive working tree (uncommitted in the
ClaudeCode repo — Drive's track record says commit). Alternate climax photos
if Harv prefers: Alviso sunset `a2b30b93…` (already bundled), starlight moon
`9bac8c31…`. Optional: a hood/filter-thread detail, per-part hover highlights.

---

## 2026-08-12 (2) — the sheen (animated gradient name) — commit 5c42acc

**Harv's brief:** pasted a React/framer-motion "AnimatedText" gradient-
shine component and asked for it on "HARV BALU," with a free hand to fit
the design. Ported the *effect* to pure CSS in `landing.css` (site is
static, not React), retuned from a 1s black/white flash to the
Observatory's register: every **10s** a narrow band of **heated gold**
with a trailing afterglow sweeps the starlight letters left→right
(`name-sheen`, 400% background, 2.6s delay, rest = pure starlight).
`.name:hover` now **ignites** (brightness 1.04 + heated-gold aura, .7s)
per the site's ignition grammar.

**Traps engineered around (remember these):**
- ⭐ `text-shadow` paints OVER gradient-clipped text in WebKit — the
  name's gold halo moved to `drop-shadow` filters inside the
  `@supports (background-clip: text)` block.
- ⭐ `resolve`'s `to` keyframe used to pin `filter` forever (fill both);
  it now **omits filter** so the property releases to base after the
  entrance and hover can transition it. The `from` filter list mirrors
  the base list shape (blur, brightness, 2× drop-shadow at zero alpha)
  to stay interpolable.
- Paint-only constraint: NEVER animate the name's geometry (size,
  spacing) — the void-water canvas measures the DOM rect for the mirror.
- `.name::selection` resets fill to void so selected glyphs don't stay
  gradient over the gold highlight.
- Reduced motion: global .01ms/1-iteration reset lands the sheen on its
  base `background-position: 100%` = solid starlight. Fallback browsers
  keep the original solid name + text-shadow.

Verified local (band sweep across two screenshots, hover bloom, 375px
mobile, zero console errors) and live (index references
`landing.css?v=de86f756bf`, `name-sheen` ×2 in served CSS). DESIGN.md
Display entry + Motion Summary updated. Impeccable gradient-text
finding classified intentional (user-requested effect); the 5 font-size
findings are the standing 560px-compaction set.

---

## 2026-08-12 (1) — THE VOID breathes (ambient water) — commit f3f7eb7

**Harv's brief:** the water is beautiful but you have to click around to
get the emotion; make it wavier and alive on its own — "do some creative
stuff." Six ambient layers added to the void-water canvas, all pure
functions of t (so the reduced-motion still inherits them), all inside
the Only-Light Rule:

1. **Reflection swell** — sway ~2× wider, a third wave traveling
   shoreward, bands of light climbing the alpha (envelope × .8–1.1).
2. **Wind** — 9 bowed glint streaks (≤ .055) drifting/breathing, wrapped
   off-canvas by a padded span.
3. **Mirrored sky** — 26 twinkling starlight sparks (≤ .16) adrift on a
   slow current, same padded-span wrap.
4. **Moonglades** — each orbiting body lays a broken wobbling light path
   on the pool while above the horizon (≤ .05).
5. **Rain + groundswell** — ambient drop every 1.1–2.8s anywhere on the
   pool (12% heavy, was 2.6–5.2s near the name); soft wide swell ring
   (life 6s, ≤ .07) every 9–15s.
6. **Breath** — halo (8.5s) and resting ring (alpha + geometry) oscillate.

**Review workflow (13 agents, 5 lenses) confirmed 2 findings, both
fixed pre-ship:** `evictRipple()` spares `soft` groundswells from the
22-cap shift() so pointer play can't delete one mid-fade in a single
frame · sparks map to a padded span `(W+12)-6` like the streaks so a lit
spark never teleports across the pool at the wrap seam.

- Verified local (desktop + 375px mobile, zero console errors) and live:
  HTTP 200, void-water ×2, all layer markers present, 20 `/img/` srcs,
  zero unresolved `$vars`. DESIGN.md Void section + Motion Summary updated.
- Launch config `portfolio-dist-local` (port 8128) added to the Web
  workspace's `.claude/launch.json` for local dist preview.

---

## 2026-08-09 PM (2) — THE VOID hero SHIPPED — commit a5b7e1f

**Harv's brief:** the distilled hero "doesn't look right" alone; keep the
orbit ring, add "a planets thing," and make the floor Stranger Things'
Void: a shallow pool of black water that ripples. Mobile friendly.

- **`<canvas class="void-water">`** (z1, under ring z2 / helm z3), painted
  by the landing's last script block: waterline at the name's baseline
  (the name STANDS on the pool), sliced wobbling reflection sampled from
  an offscreen canvas text render, gold halo pooling, resting ellipse,
  ambient + pointer/touch ripples (perspective ellipses), three bodies
  orbiting the name (21/34/52s, gold/starlight tones only), mirrored in
  the pool. Cue moved from flow to absolute bottom (pool's far edge).
- **Review workflow (13 agents) confirmed 9 findings, all fixed:** canvas-
  measured reflection so no `$hero_name` ever clips + `.name` nowrap with
  a 2rem narrow floor (280px Galaxy Fold verified) · mmReduce change
  listener with a self-halting RAF loop · ctx.filter blur fallback for
  Safari ≤ 17 (five offset passes) · reflection capped above the cue on
  short viewports · name selectable again (`pointer-events: auto` vs the
  helm's none) · animationend re-measure repaints the reduced still ·
  ⭐ **the reduced-motion global rule zeroed durations but NOT
  `animation-delay`** — delayed entrances (topbar 2.3s, cue, canvas) sat
  invisible; `animation-delay: 0s !important` added.
- DESIGN.md updated (Void component, Layout, Z-ladder, Motion Summary).
- Live verified: `?v=a98496e355`, void-water present, 20 `/img/` srcs, no
  console errors desktop or mobile, touch ripple works, 0 overflow at
  390px and 280px. Detector: zero findings from the changed lines.

---

## 2026-08-09 PM — landing hero DISTILLED (name + orbit only) — commit 630ce53

**Harv's brief** (from the Web workspace session, matching his harvinder.dscloud.me
intro): "remove the pictures around it, just have my name, keep the circular
thing," Descend cue stays, photos on scroll. Ran under the impeccable skill
(distill) against the committed Observatory world.

- **Hero = name + orbit ring + Descend cue.** Removed: the three desktop
  hero-body plates (tile--1/2/3 absolutes + dim/flare rules), overline,
  tagline, tally. Cue retimed 2.55s → 2.3s (arrives with the topbar, one
  beat after the name resolves). The 900px meander rules now cover ALL
  tiles (dropped the `:nth-of-type(n+4)` gate), so plates 01–03 open the
  descent column; template JS lost the mmWide ignite branch.
- **DESIGN.md trued up** (Label tracking list, Landing layout bullet,
  Z-ladder, Plate ignition, Motion Summary choreography). Detector findings
  on landing.css are the SAME 13 incumbent lines as before the edit (prose-
  documented sizes the frontmatter ramp misses + 2 CSS-file "broken-image"
  mis-fires) — classified intentional, zero findings from the changed lines.
- ⭐ **The `photo` SMB share refused to mount** (AppleScript -5014, twice;
  the `web` share mounted fine) → export bundled 0 landing images and fell
  back to WP-host URLs, which would break the offline-safe front door.
  **Fix that keeps the exporter honest:** stage the 20 live derivatives out
  of `~/Sites/harv-portfolio/img/` into the NAS `.portfolio` layout in a
  temp dir, then drive `export_static.main()` with `config.THUMB_DIR` /
  `DISPLAY_DIR` rebound to the stage (they are read-at-call module globals).
  Result: `bundled 20 landing-critical images`, srcs back to `/img/`.
- **Deploy:** rsync dist → `~/Sites/harv-portfolio` with `--exclude` for
  .git/.gitignore/.vercel/README.md/robots.txt (repo-only files a bare
  `--delete` would kill) → commit `630ce53` → push → auto-deploy. Live
  verified: `?v=a669e931c1` CSS, 0 overline/tagline/tally, 20 `/img/` srcs,
  0 tile--1 rules in served CSS, no console errors, Playwright shots of
  hero/descent/mobile.

---

## 2026-08-05 PM — "MERIDIAN" redesign SHIPPED (impeccable skill, full loop)

**Harv's brief:** camera photos only (AI out "for now"), /work "more animatic,
smooth, dramatic," obvious next/prev in the viewer, free hand, use impeccable.

- **Camera-only:** `EXCLUDED_FOLDERS = {"AI Generated"}` in export_static.py —
  the DB and admin curation untouched; the exporter filters. Site = **240
  frames · 6 collections · epochs 2003–2023**. ⭐ Cosmology VERIFIED camera
  (Canon Rebel XT/T5i EXIF) — it is astrophotography, NOT AI; only the
  "AI Generated" folder (210 Midjourney-style PNGs) is excluded. About copy
  overridden in the exporter (ABOUT_HTML_STATIC) to drop the AI mention.
- **/work = THE MERIDIAN** (impeccable concept-seed assigned candidate 7/7,
  seed 6f9fe34d): collections as survey stations on one gold line that draws
  with scroll (transform-only, rAF), newest last-observation first, descending
  to a FIRST LIGHT terminus. Station = plate + Italiana name + "Chart N ·
  n frames · epoch" data line. Chart numbers match collection pages.
- **Collection pages = CHARTS**: Observatory voice (Italiana + Fragment Mono
  via `body.inner` var re-pointing — cream tokens stay for admin), ignition
  ember→lit reveals, hover bloom, gold return arrow.
- **Lightbox v2**: gold tabular counter "042 / 119", epoch caption, drawn
  one-stroke SVG chevrons/×, direction-aware two-layer crossfade travel,
  swipe, side click-zones, arrow keys, focus trap, reduced-motion = instant.
- **Server parity:** server.py `_page_work`/_page_collection emit the same
  meridian/chart markup (templates shared). Compile-checked.
- ⭐ **Asset URLs are content-hashed** (`?v=<sha1[:10]>`) by the exporter —
  vercel.json caches /static/ 1h, so unhashed redeploys could pair new HTML
  with stale CSS. This also defeats the browser-pane's cache wedge.
- ⭐⭐ **rAF STARVES in throttled contexts** (the in-app pane wedges its
  compositor; background tabs too) — never gate state-correctness on
  requestAnimationFrame. Use `void el.offsetWidth` forced reflow to commit
  transition origins. Found because the pane froze mid-verify.
- ⭐ **Impeccable finish loop ran fully**: detector (0 findings ×2), fresh-
  context reviewer (shipped agent types absent → degraded reference in a
  general-purpose agent), 5 material findings ALL real (travel resting
  34px off-center — from-* classes later in cascade than .is-on; unstyled
  colophon; no focus trap; reduced-motion 560ms occlusion; topbar/title
  interleave), fixed in one batch, redeployed, verdict pass + DESIGN.md
  documenter spawned. Playwright (system python3) shoots the LIVE site for
  screenshot files — the pane can't produce files.
- Commits: 447b160 (redesign) · c5ebd79 (review fixes). Live at
  https://harvbalu.net/work — verify with `?x=$RANDOM` cache-buster.

---

## 2026-08-05 — portfolio/ DEPLOYED: https://harvbalu.net

**Custom domain LIVE** (GoDaddy-registered 2026-08-05, DNS stays at GoDaddy —
nameservers NOT moved, so MX/email remain addable there later):

| Record | Name | Value |
|---|---|---|
| A | `@` | `216.198.79.1` (was GoDaddy parking) |
| CNAME | `www` | `f2b575ea1c46149a.vercel-dns-017.com.` (was `harvbalu.net.`) |

Untouched: both NS, SOA, `_domainconnect`, `_dmarc` TXT. **No MX existed**, so
nothing email-related was at risk. `www` is a **308 redirect → apex** (set via
API; Vercel defaults to serving BOTH, which would be duplicate content).
Let's Encrypt cert auto-issued (CN=harvbalu.net, expires 2026-11-03).
Vercel reports `misconfigured: false` for both names.
⭐ Vercel's rank-1 advice lists TWO apex IPs but **one A record is enough** —
it reported configured with just `216.198.79.1`.
⭐ This CLI version has no "add domain to project" command
(`vercel domains add` is account-level) → use the REST API
`POST /v10/projects/<project>/domains` with the CLI's own token from
`~/Library/Application Support/com.vercel.cli/auth.json`.
⚠️ After the change the Mac's local resolver kept the old parked IPs for a
while though 1.1.1.1/8.8.8.8 had updated — verify with
`curl --resolve harvbalu.net:443:216.198.79.1` instead of assuming breakage.

Original vercel.app URL still works: https://harv-portfolio.vercel.app

---

## 2026-08-05 — portfolio/ deployment details

**Dedicated accounts, kept strictly separate from all realtor infra:** GitHub
`harvbalu-Photo` (private repo `harv-portfolio`) + Vercel `harvbalu-photo`
(scope `harvbalu-photos-projects`). No contact info anywhere on the site
(Harv's call — nav is Work/About only; contact section removed from
`templates/index.html`).

- **Pipeline (all in `portfolio/`):** `export_static.py` renders /, /work, 7
  `/c/<ascii-slug>` pages + 404 through the SAME templates/queries as the live
  server → `dist/`; `publish_images.py` copies the 898 public derivatives
  (450 photos × thumb+display, 83 MB) from `/Volumes/photo/.portfolio/` straight
  into `/Volumes/web_packages/wordpress/wp-content/uploads/portfolio/` over SMB
  (bypasses Wordfence's ≥7s REST throttle AND keeps the WP media library clean).
  Build metadata → `portfolio/build/manifest.json` (not deployed).
- **Hybrid image hosting (Harv's design):** the 21 landing-critical images
  (14 collage + 7 covers, 2 MB) are BUNDLED into the deploy at `/img/` so the
  landing + /work render even when the home Synology (~90% uptime) is offline;
  collection grids embed from `harvinder.dscloud.me/blog/wp-content/uploads/portfolio/`.
- **Deploy repo:** `~/Sites/harv-portfolio` (rsynced OUT of Google Drive —
  Vercel hangs on Drive paths). Commits authored as
  `Harv Balu <harvbalu-Photo@users.noreply.github.com>`.
  ⭐ gh's credential helper only serves the ACTIVE account, so the repo has a
  LOCAL `credential.helper` that runs `gh auth token -u harvbalu-Photo` at push
  time — pushes work while `User8888-Level3` stays the CLI default (restored).
- **Update flow:** re-run `export_static.py` (+ `publish_images.py` if photos
  changed) → rsync `dist/` → `~/Sites/harv-portfolio` → commit → **`git push`.
  That's it — auto-deploy handles production.** (Manual escape hatch:
  `vercel deploy --prod --yes --scope harvbalu-photos-projects` from that dir.)
- ✅ **Auto-deploy CONNECTED + PROVEN** (2026-08-05): pushing `robots.txt` with
  no CLI deploy produced a Ready Production deployment 23s later serving that
  file. ⭐ `vercel git connect` from the CLI FAILS on a fresh private repo —
  the fix is the dashboard: project → Settings → Git → pick GitHub → **Install**
  (installs the Vercel GitHub App on harvbalu-Photo) → **Connect**.
- ⚠️ gh device-login from a session: `printf '\n' | script …` does NOT deliver
  Enter to gh — use `expect` (spawn → expect "Press Enter" → send \r).

---

## 2026-07-30 — portfolio/: "Observatory" redesign + public-hosting auth + mount resilience

- **Landing REDESIGNED** (Harv rejected the cream Collienne homage): now "Observatory" —
  #050505 void, Italiana/Fragment Mono, gold orbit ring, plates igniting on descent.
  Won a 3-designer / 3-judge panel 3-0 (candidates preserved in `portfolio/candidates/`,
  old landing in `candidates/_rejected-cream/`). Inner public pages harmonized to the
  void via scoped body-class token overrides in style.css (admin stays cream).
- **Public-hosting auth SHIPPED + tested**: `PORTFOLIO_PUBLIC=1` (distrust localhost)
  + `PORTFOLIO_ADMIN_TOKEN` → /admin/login (HttpOnly cookie, 10/10min throttle,
  logout), `PORTFOLIO_BASE_URL`, global `Referrer-Policy: same-origin`. README §Hosting.
- **Mount resilience**: macOS strands dead stubs at /Volumes/photo and remounts at
  photo-1 — config._resolve_mount() now auto-detects; DB stores canonical
  /Volumes/photo paths, translated at runtime (canon_path/real_path).
- Visitor-facing filenames removed everywhere (lightbox/share/markup) — date-only.
- ⚠️ Browser-pane gotcha again: native scroll wedges it; JS-scroll screenshots go
  stale until a real re-navigation. Headless Chrome full-page shots inflate vh gaps.
- OPEN: Harv reviews new landing · hosting home decision (Synology proxy vs n8n VPS)
  · contact email still realtor address · still uncommitted in git.

---

## 2026-07-23 — NEW: `portfolio/` — HARV BALU portfolio site (separate app)

A second, independent app now lives in `Photography/portfolio/` (own SPEC.md + README.md —
**read those first**; do not confuse with the photo_index dashboard above).

- **What:** gregorcollienne.com-style public portfolio + admin panel + expiring share links
  for the `/Volumes/photo` NAS share (NOT Pictures-Vol3). Stdlib server on **127.0.0.1:8770**
  (`Portfolio.command`), SQLite at `portfolio/data/portfolio.db` (gitignored, rebuildable),
  derivatives on-NAS at `/Volumes/photo/.portfolio/`.
- **Privacy model (tested end-to-end):** default private; per-FOLDER-membership rows (same
  content in N folders = N rows, one visibility each; content serves if ANY row public);
  content also living in Family/Customers/PhotoLibrary is never auto-published
  (`SENSITIVE_FOLDERS` + `_demote_sensitive`, demoted 112 on first full index).
  Share tokens are photo-bound, expire (24h/7d/30d/custom/never), revocable.
- **State:** 3,824 rows indexed (3 pre-existing corrupt Family JPEGs skipped), 450 public,
  7 public collections. Identity: HARV BALU, Instagram dropped, contact email = realtor
  address pending Harv's "decide later".
- **⚠️ Before any public hosting:** flip `ALLOW_LOCALHOST_ADMIN=False` + set `ADMIN_TOKEN`
  + real `BASE_URL` + HTTPS — see README "Before hosting" section.

---

## 2026-07-16 — dashboard repair + redesign (read before touching the site)

**Google Drive strips symlink targets in this folder.** It zeroed both `site/thumbs` and
`.venv/bin/python*`, which killed every thumbnail and stopped the server from launching.
Expect this to recur.

- `photo_server.py` now serves `/thumbs/` **directly from `config.THUMB_ROOT`**, so the
  `site/thumbs` symlink is no longer load-bearing. It also sends `Cache-Control`
  (`no-cache` for pages, 1-year immutable for SHA-1-addressed thumbs) — before this,
  browsers showed days-stale pages after every regeneration.
- If the venv dies: relink `python{,3,3.13}` → `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`.
- **Open via `Photo-Dashboard.command`, never `file://`** — search + Open File/Folder need the server.

**"Light Table" redesign** — graphite `#08090b` + focus-peaking lime `#cdf24c`,
Bricolage Grotesque / Instrument Sans / Geist Mono, AF corner-bracket tile hovers,
`FR 01` EXIF chips. Done in `photo_index/templates/` then regenerated (index + 13 year
pages); `duplicates.html` inherits it via the shared stylesheet.

⚠️ **CSS landmine:** never combine `background-attachment: fixed` with a blurred sticky
header — that pair black-screens Chrome's compositor on macOS. The current CSS avoids
both; grain is a fixed-position pseudo-element instead.

⚠️ **Uncommitted:** these changes are working-tree only. Committing is recommended given
Google Drive's track record in this folder.

Full writeup: `session-2026-07-16-photo-archive-redesign.md` (GoogleDrive-ClaudeCode memory)
· OneNote **Photography → Claude-Photo**.

---

## PICKUP NOTE (read this first, future-me)

Project is done. No active work.

If Harv says *"continue photography index"*, he almost certainly wants one of these:

1. **"Re-index / include new photos"** → `./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --workers 12`. mtime-skip is cheap; re-running on existing years is almost free.
2. **"Run dedup again"** → `build_index.py decide --out decisions.json` → inspect → `apply decisions.json --apply`. The 2,928 remaining similar clusters will still be there waiting for visual review.
3. **"Open the dashboard"** → Run `Photography/Photo-Dashboard.command` (double-clickable) OR start the server yourself: `cd Photography/site && ../.venv/bin/python -m http.server 8765 --bind 127.0.0.1`, then open http://127.0.0.1:8765/.
4. **"Purge #recycle"** → `rm -rf "/Volumes/Pictures-Vol3/#recycle/dup-cleanup-2026-04-23"` (~52.1 GB). **ASK FIRST** — this is destructive. Everything in there was moved by this project.
5. **Phase 2 scope expansion** → point indexer at topical folders (Asha, Drone, Fam, etc.) or library sources (iPhone.photoslibrary, M1-MAC-Backup). Schema already supports cross-source dedup.

**Before touching code:** `./.venv/bin/pytest tests/ -q` — should be 41 passing.

**Known gotcha:** Harv uses OneNote in dark mode. If you generate any OneNote page, NEVER put `background:` on a `<table>` wrapper — only on specific header cells, always paired with explicit light `color:`. Body cells stay transparent so OneNote's theme handles contrast. See `feedback-onenote-dark-mode.md` in memory.

**Orphan to ignore:** the empty `Computers > Photography` section in OneNote was a mistake I made on 2026-04-23. Harv was going to delete it manually (Graph API can't delete sections). Don't recreate it — Harv's real notebook is **Photography > Claude-Photo**.

---

## Where we ended up

**26,438 files indexed** across 2013–2025 (6 errors, all Synology-side file corruption).
**23,811 active** after dedup.
**2,621 files moved to `#recycle`** (~52.1 GB reclaimable).
**41 tests passing.**

### Per-year indexing timing (M3 run, 2026-04-22/23)

| Year | Files | Time | Rate |
|---|---|---|---|
| 2013 | 874 | 2m56s | 4.9/s |
| 2014 | 1,258 | 6m02s | 3.5/s |
| 2015 | 835 | 12m33s | 1.1/s |
| 2016 | 4,367 | 28m11s | 2.6/s |
| 2017 | 2,149 | 11m54s | 3.0/s |
| 2018 | 278 | 1m11s | 3.9/s |
| 2019 | 835 | 4m22s | 3.2/s |
| 2020 | 1,830 | 47m51s | 0.6/s |
| 2021 | 2,695 | 18m48s | 2.4/s |
| 2022 | 5,493 | 30m27s | 3.0/s |
| 2023 | 3,481 | 27m28s | 2.1/s |
| 2024 | 1,790 | 16m56s | 1.8/s |
| 2025 | 553 | 4m33s | 2.0/s |
| **Total** | **26,438** | **~3h13m** | **2.3/s avg** |

### Dedup cleanup passes

| Pass | Exact groups | Similar raw+JPG | Files moved | Space |
|---|---|---|---|---|
| 1 | 1,974 | 222 | 2,563 | 51.46 GB |
| 2 | 0 | 58 | 58 | 651.7 MB |
| **Total** | **1,974** | **280** | **2,621** | **~52.1 GB** |

### What's left in `duplicates.html` (2,928 similar groups not auto-touched)

| Category | Groups | Why skipped |
|---|---|---|
| sequential_pair | 855 | Sequential captures — likely distinct frames |
| other | 802 | Mixed, ambiguous |
| video_burst_small | 387 | 2–3 videos per group |
| sequential_small_burst | 319 | 3–5 burst frames |
| cross_year | 216 | pHash false positive likely |
| video_burst_large | 129 | 4+ videos |
| cross_event | 113 | Same file copied across folders |
| sequential_medium_burst | 80 | 5–15 burst frames |
| sequential_large_burst | 6 | 15+ burst frames |

These need human eyes — auto-deleting bursts or cross-year matches would risk real content loss.

---

## Accessing the dashboard

**Easy (double-click, recommended):** `Photography/Photo-Dashboard.command` — starts the HTTP server and opens the browser. Keeps running until you close its Terminal window. First run requires right-click → Open to bypass macOS Gatekeeper.

**Manual:**
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography/site
../.venv/bin/python -m http.server 8765 --bind 127.0.0.1
# then open http://127.0.0.1:8765/
```

**Direct file:// (limited):** open `site/index.html` directly in Safari. Year pages + thumbnails work, but **global search breaks** because fetch() is CORS-blocked on `file://`.

Stop server: `pkill -f "http.server 8765"`.

---

## Commands reference

```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography

# Index new photos (incremental)
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --workers 12

# Limit to first N files (smoke tests)
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --limit 50 --workers 4

# Regenerate site + search JSON + duplicates.html
./.venv/bin/python build_index.py html

# Skip duplicates.html regen (faster during indexing)
./.venv/bin/python build_index.py html --no-dups

# Auto-decide dup groups
./.venv/bin/python build_index.py decide --out decisions.json

# Dry-run apply
./.venv/bin/python build_index.py apply decisions.json

# Real apply (destructive, moves to #recycle)
./.venv/bin/python build_index.py apply decisions.json --apply

# Tests
./.venv/bin/pytest tests/ -q
```

**Nuclear reset (erases all index state but NOT the source photos):**
```bash
rm index.db index.db-wal index.db-shm
rm -rf /Volumes/Pictures-Vol3/.index/thumbs
rm -rf site/years site/photo site/assets/search-*.json
```

---

## Decisions locked (for any v2 continuation)

See `docs/plans/2026-04-22-photography-index-design.md`. Summary:

- **Scope phase 1:** year folders 2013–2025 only.
- **Thumbs on Synology:** `/Volumes/Pictures-Vol3/.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg` (944 MB used).
- **Metadata DB:** local SQLite at `Photography/index.db`, WAL mode.
- **File types:** JPG/PNG/HEIC (Pillow) + CR2/DNG (Pillow native) + CR3/ARW/NEF/ORF/RW2 (exiftool preview) + MP4/MOV (ffmpeg frame grab).
- **Captured:** SHA-1 + pHash + full EXIF in one pass.
- **Threaded indexer:** 12-worker `ThreadPoolExecutor` + single-writer SQLite thread, 100-row batched commits.
- **Retry:** `@smb_retry()` 3 attempts, 2s exponential backoff on `OSError` + `TimeoutExpired`.
- **Deletions:** never `rm`; always `mv` to `#recycle/dup-cleanup-YYYY-MM-DD/` with numeric `__dupN` collision suffix. DB `deleted_at` set. Append-only `logs/deletions.jsonl`.

---

## Pending housekeeping for Harv (his call, no rush)

- [ ] **Purge `/Volumes/Pictures-Vol3/#recycle/dup-cleanup-2026-04-23/`** once confident (~52.1 GB).
- [ ] **Manual review the 2,928 remaining similar clusters** via `duplicates.html` — export decisions.json → `apply --apply`.
- [ ] **Delete the empty orphan section** `Computers > Photography` in OneNote client (Graph API can't; I already deleted my misplaced page from it).
- [ ] **Fix/relocate 6 corrupted 2016-07-16 files** on Synology (3 CR2 with malformed XMP, 2 CR2 all-binary-zeros, 1 MOV missing moov atom). Synology-side damage, not our bug.

---

## Commits on main branch (User8888-Level3)

| SHA | Milestone |
|---|---|
| `058c140` | M1+M2 — threaded indexer + 2024 archive |
| `28181a1` | M2 docs — SESSION-STATE handoff |
| `458e458` | M3 — full archive + search UI |
| `f412140` | M4 — duplicate detection + review UI |
| `8802e68` | auto-decide + apply_decisions (M5 Tasks 24-26) |
| `509935e` | M5 pass 1 — 2,563 dups moved (51.5 GB) |
| `a820558` | M5 pass 2 — 58 more raw+JPG pairs (+651.7 MB) |

---

## Pointers

- Design doc: `docs/plans/2026-04-22-photography-index-design.md`
- Implementation plan: `docs/plans/2026-04-22-photography-index.md`
- Memory pointer: `project-photography-index.md` in Claude auto-memory.
- OneNote record: **Photography notebook > Claude-Photo section** (NOT Computers > Photography).
- Data source: `smb://172.22.2.147/Pictures-Vol3` (24 TB, 19 TB used, mounted at `/Volumes/Pictures-Vol3`).
- Dashboard launcher: `Photo-Dashboard.command` (double-clickable).
