# THE ANNUAL — editorial counterpoint

**Concept, one sentence:** The landing is designed as the cover and opening spread of a
photography annual — a warm-paper masthead band wraps a deep-ink field where the
photographs hang as numbered, gold-captioned plates.

**The one thing a visitor remembers:** the cover plate slicing upward through the paper
masthead band — a photograph physically breaking the book's cover.

**Type:** Fraunces variable (SOFT 0, WONK 1 — wonky art-book serif) for masthead/display,
Fragment Mono for folios and plate captions. No Anton, no Inter, no Space Grotesk.

**Palette tokens:** ink `#0E0D0B` · contents spread `#131009` · paper `#EDE6D8` ·
foil gold `#D4AF37` (on ink) · impressed gold `#6D5411` (on paper) · dim `#B7AF9F`.

**Motion story:** load — the name foil-stamps in, character by character (tiny inline
script, delay per glyph); scroll — plates and TOC rows rise 24px on IntersectionObserver;
hover — plates lift brightness + their plate number ignites, TOC covers scale 1.02 while
captions nudge; only transform/opacity/filter are ever animated. Reduced motion collapses
everything to visible-static; no-JS shows the full page.

**Mobile (verified live at 375):** spine hidden, masthead stays one line, the woven
12-column spread collapses to a full-width staggered column (alternating 1/12 – 2/13),
TOC rows stack caption-over-cover; zero horizontal scroll.

**Risks:** plate numbering uses CSS counters on server markup (safe if tile markup holds);
`display: contents` on the folio wrapper (baseline-supported); fixed nav/spine use
`mix-blend-mode: difference` — plain color, no backdrop-filter, macOS-Chrome-safe.
The seam overlap is geometry-locked (plate ≤ 66.7% grid, foot text ≥ 68%) so no collision
at any width. `.collection-cover`/`.tile img` set `height:auto` to beat height attributes.
