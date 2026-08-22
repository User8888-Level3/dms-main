# Landing-page redesign brief — HARV BALU photography portfolio

## The verdict being overturned
The current landing (cream field, giant Anton "HARV BALU", scattered parallax collage —
a Gregor Collienne homage) was REJECTED by the owner: "I don't like the way it looks…
you're gonna have to do a better job. You have a free hand — be creative."
Do NOT produce another Collienne clone. Do not produce generic AI-slop either
(no Inter/Space Grotesk, no purple gradients, no cookie-cutter hero-and-cards).
This will be shown publicly to external visitors — it must feel like a real
photographer's flagship site, unforgettable and personal.

## Who / what this is
Harv Balu — Bay Area photographer. The PUBLIC archive this landing fronts
(real inventory, use it to drive the design):
- **Cosmology · 119** — moons (wolf moons, eclipses), night skies, long exposures. Dark, luminous.
- **AI Generated · 210** — his AI artwork: photoreal hummingbirds on black, elephants in
  monochrome rain, fireworks over skylines, surreal painterly pieces. Bold, saturated-on-dark.
- **Cancún · 35** — turquoise water, white hotels, gulls.
- **Niagara Falls · 32** — mist, rushing water, boats.
- **Monterey Bay Aquarium · 36** — jellyfish on deep blue, fish, kelp. Electric blues.
- **New York City · 14**, **Alviso Marina · 4** — skylines, golden-hour marsh sunsets.
KEY INSIGHT: the archive is overwhelmingly LOW-KEY and LUMINOUS — night skies, deep
aquarium blues, sunsets, black-background artwork. A light/cream page fights the work.
Photographs-as-light-sources is the natural move (but you decide; commit hard either way).

Brand context (may use, not mandatory): his personal monogram is gold `#D4AF37` on
near-black `#0E0D0B`. Site name: HARV BALU. Contact: a mailto (template var). No Instagram.

## Hard technical contract (all candidates MUST respect)
Server renders `templates/index.html` via Python `string.Template.safe_substitute`.
Available `$vars` (use what you want, ignore the rest; NO other vars exist):
- `$hero_name` — "HARV BALU" (escaped)
- `$collage_tiles` — up to 14 `<figure class="tile tile--N" data-speed="0.xx"><img
  src="/media/thumb/<sha1>.jpg" alt="" width="W" height="H" loading="eager|lazy"></figure>`
  elements, newest artwork first. Thumbs are 400px-edge JPEGs. You may restyle/relayout
  `.tile` freely (grid, strip, orbit, stack…) — you do NOT control their markup.
- `$collection_cards` — the public collections as `<a class="collection-card"
  href="/c/…"><img class="collection-cover" src="/media/display/<sha1>.jpg" …>
  <span class="collection-caption">01 — NAME · COUNT</span></a>` (display = 1600px JPEGs).
  Restyle freely; you do not control the markup.
- `$collection_count` (int), `$photo_total` (int, public photos)
- `$about_html` — one `<p>` bio (all-caps text)
- `$contact_email`, `$year`, `$site_name`
- LITERAL `$` in CSS/JS must be written `$$`. Prefer avoiding `$` in JS entirely.

Constraints:
- Fonts: Google Fonts `<link>` ONLY (pick distinctive, characterful faces — your call;
  avoid Inter/Roboto/Arial/system/Space Grotesk). No other external assets, no CDN JS,
  no frameworks, no build step. Vanilla ES2020 max.
- ⚠️ NEVER combine `background-attachment: fixed` with a blurred sticky element, and no
  `backdrop-filter` on sticky/fixed elements (macOS Chrome compositor black-screen).
- Respect `prefers-reduced-motion` (motion collapses to opacity/none).
- Mobile-first responsive down to 375px; no horizontal scroll; touch-friendly.
- Performance: this page ships ≤14 thumb images + ≤7 display covers. Animate only
  transform/opacity/filter; use `will-change` sparingly; no layout thrash on scroll.
- Nav must link to `/work` and expose About + `mailto:$contact_email` somewhere elegant.
- Keep `<html lang="en">`, viewport meta, a `<title>`, meta description, favicon may be
  inline SVG data URI. Accessibility: real landmarks, focus-visible states, alt="" on
  decorative imagery, AA contrast for text.

## Deliverables (per candidate)
Write EXACTLY these files (nothing else):
1. `candidates/<name>/index.html` — full replacement landing template (self-contained
   design; may include a small inline <script> at the end, or none).
2. `candidates/<name>/landing.css` — the page's stylesheet (loaded as
   `/static/landing.css` in your template; write the link tag that way).
3. `candidates/<name>/NOTES.md` — ≤25 lines: the concept in one sentence; the one thing
   a visitor will remember; type + palette tokens; motion story (load → scroll → hover);
   mobile strategy; any risks.
Your index.html must reference ONLY `/static/landing.css` (+ Google Fonts) — do not
reference style.css or app.js; the landing stands alone.

## Bar
This is a flagship. One clear concept executed with precision beats three timid ideas.
Design for HIS photographs (moons, jellyfish, gold hour, black-background art), not for
a generic portfolio. Make the first five seconds unforgettable.
