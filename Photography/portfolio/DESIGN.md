---
name: HARV BALU — Observatory
description: A pitch-black night gallery where the photographs are the only light — plates, charts, and one drawn meridian.
colors:
  void: "#050505"
  starlight: "#F2EDE0"
  reading-cream: "#C9C2B1"
  dim: "#A39C8B"
  dim-2: "#8A8375"
  gold: "#D4AF37"
  gold-bright: "#EED688"
  gold-dim: "rgba(212, 175, 55, .55)"
  hairline: "rgba(212, 175, 55, .22)"
typography:
  display:
    fontFamily: "'Italiana', 'Didot', 'Bodoni MT', serif"
    fontSize: "clamp(3.3rem, 12.5vw, 10.8rem)"
    fontWeight: 400
    lineHeight: 0.98
    letterSpacing: "0.045em"
  headline:
    fontFamily: "'Italiana', 'Didot', 'Bodoni MT', serif"
    fontSize: "clamp(3rem, 9vw, 7.5rem)"
    fontWeight: 400
    lineHeight: 1.02
    letterSpacing: "0.05em"
  title:
    fontFamily: "'Italiana', 'Didot', 'Bodoni MT', serif"
    fontSize: "clamp(1.7rem, 3.6vw, 3rem)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "0.06em"
  body:
    fontFamily: "'Fragment Mono', ui-monospace, 'SFMono-Regular', monospace"
    fontSize: "0.74rem"
    fontWeight: 400
    lineHeight: 2.15
    letterSpacing: "0.13em"
  label:
    fontFamily: "'Fragment Mono', ui-monospace, 'SFMono-Regular', monospace"
    fontSize: "0.6rem"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: "0.3em"
rounded:
  none: "0px"
spacing:
  pad-x: "clamp(1.25rem, 6vw, 6rem)"
  field-gap: "clamp(14px, 1.6vw, 24px)"
  section-y: "clamp(6rem, 15vh, 11rem)"
  station-y: "clamp(2.6rem, 7vh, 5.5rem)"
  plate-stack: "clamp(96px, 17vh, 230px)"
components:
  nav-link:
    textColor: "{colors.dim}"
    typography: "{typography.label}"
    padding: "0.55rem 0.15rem"
  nav-link-hover:
    textColor: "{colors.gold-bright}"
  station-name:
    textColor: "{colors.starlight}"
    typography: "{typography.title}"
  station-name-hover:
    textColor: "{colors.gold-bright}"
  counter:
    textColor: "{colors.gold}"
    typography: "{typography.label}"
  skip-link:
    backgroundColor: "{colors.void}"
    textColor: "{colors.gold}"
    rounded: "{rounded.none}"
    padding: "0.7rem 1.2rem"
  lightbox-button:
    textColor: "{colors.gold}"
  lightbox-button-hover:
    textColor: "{colors.gold-bright}"
---

# Design System: HARV BALU — "Observatory"

## Overview

**Creative North Star: "The photographs are the only light."**

The public site is an astronomer's private observatory after dark. The page is
a `#050505` void under a fixed, sparse starfield; the photographs hang in it as
celestial bodies — dimmed at rest, ignited on approach — and every piece of
interface is an instrument marking drawn around them in monogram gold. Type
speaks in two voices only: Italiana, a hairline high-contrast serif, for
designations (names, titles, chart headings), and Fragment Mono, uppercase and
widely tracked, for the log lines that annotate them. The register is a
survey log-book: photographs are *observations* and *plates*, collections are
*charts* on *The Meridian*, dates are *epochs*, the about section is *Field
Notes*, the footer signs off with coordinates.

Two page families share the world. The landing (`templates/index.html` +
`static/landing.css`) descends from the hero name through numbered plates into
The Atlas. The archive (`templates/work.html`, `templates/collection.html` +
`static/style.css` + `static/app.js` + `static/instrument.js`) opens on The
Instrument — a reflex camera drawn in gold light that assembles, turns, comes
apart, closes, and carries the visitor down its optical axis to the sensor,
where a photograph is recorded — then becomes The Meridian — every collection
as a station on one gold survey line that draws itself as the visitor
descends, newest epoch first, ending at *First light* — and each chart page
is a masonry field of frames opened by the lightbox viewing instrument. The form refuses
the category-default same-size card grid everywhere: plates meander, stations
alternate across the line, atlas cards follow an editorial 12-column cycle.

Motion is a single grammar: things *ignite*. Frames arrive as embers
(dark, slightly small, desaturated) and warm to full luminance; the meridian
ink draws with scroll; lightbox frames travel directionally and bloom on
arrival. All scroll- and entrance-driven motion writes only `transform`,
`opacity`, and `filter`, and the whole system collapses to visible-and-static
under `prefers-reduced-motion` — in CSS and in every JS branch.

**Key Characteristics:**
- Void-black ground; warm star-white text; gold reserved for instrumentation.
- Photographs are the brightest objects on screen — the UI never outshines them.
- Two typefaces, one weight (400); microcopy is uppercase tracked mono.
- Sharp corners everywhere; light *blooms*, nothing casts a drop shadow.
- Ignition motion grammar; transform/opacity/filter only; reduced-motion safe.
- Log-book voice; epoch-only captions; Roman numerals for charts, zero-padded
  Arabic for frames.
- No contact information anywhere on the public surface.

**Implementation boundary.** `static/style.css` opens with a cream "Editorial
Cream" `:root` (paper `#F2EFE9`, Anton / Instrument Sans / Geist Mono). That is
the **private admin tool's** system, not this world. Public inner pages get the
Observatory by token override under `body.inner` (and `body.share-body` /
`body.expired-body`) plus the "OBSERVATORY INNER PAGES" section. New public
surfaces must set `body.inner` (or restate the tokens, as `landing.css` does);
never style a public page with the bare cream `:root` values, and never leak
Observatory styling into `body.admin`. Templates are shared with the live
private server: `string.Template` `$var` placeholders must be preserved.

## Colors

A single-hue instrument panel: one gold family for markings over a warm
grayscale that runs from void to star-white.

### Primary

- **Monogram Gold** (#D4AF37): the instrument color — brand monogram, plate
  labels, counters, ticks, the meridian line and ink, data numerals inside dim
  copy (`.au` spans), section numerals, chart-return links, lightbox chrome,
  focus outlines, selection background, the signoff. Never body copy.
- **Heated Gold** (#EED688): hover/approach state of anything gold or any
  interactive text — links, station names, lightbox buttons. Also the warm
  stars in the starfield's second layer.
- **Gold Dim** (rgba(212, 175, 55, .55)): quiet gold — the brand middot,
  underline decoration color, video-badge borders, ink gradient tail.
- **Gold Hairline** (rgba(212, 175, 55, .22)): 1px rules and underlines at
  rest (seal rules, `.all` link underline). The colophon's top border uses a
  slightly fainter rgba(212, 175, 55, .14).

### Neutral

- **The Void** (#050505): the only background. Scrims are the void again at
  opacity — topbar gradients fade from rgba(5,5,5,.92–.97) to transparent, the
  lightbox backdrop is rgba(4,4,4,.985), the video badge sits on
  rgba(5,5,5,.72). There is no second surface color.
- **Starlight** (#F2EDE0): primary text — headings, station names, hero name,
  lightbox note links. Warm star-white; the build never uses #FFFFFF.
- **Reading Cream** (#C9C2B1): long-form reading copy — the landing bio and
  the lightbox caption line (hardcoded twice, not a custom property).
- **Dim** (#A39C8B): secondary mono copy, AA on the void — nav at rest,
  taglines, captions, obs-data lines, station data.
- **Dim 2** (#8A8375): tertiary microcopy, AA-large only — tallies, section
  subtitles, legal/coords, the counter's "/ total", terminus word.

### Named Rules

**The Only-Light Rule.** The photographs are the brightest things in the room.
Images rest slightly dimmed (`filter: brightness(.88–.9)`; hero-orbit plates at
`opacity: .88`) and reach or exceed full luminance (brightness 1.02–1.07) only
on ignition, hover, or in the lightbox. No UI element may glow brighter than a
lit plate; the starfield stays at opacity ≤ .44.

**The Instrument-Gold Rule.** Gold marks instrumentation and data — lines,
ticks, counters, labels, numerals, focus — and is never the color of a
paragraph. Inside a dim log line, only the data values go gold
(`<span class="au">240</span> frames`).

## Typography

**Display Font:** Italiana (with Didot, Bodoni MT, serif fallbacks)
**Body/Label Font:** Fragment Mono (with ui-monospace, SFMono-Regular fallbacks)

**Character:** A hairline engraver's serif for designations over a typewriter
log voice for everything else. One weight — 400 — across the entire world;
emphasis comes from size, tracking, case, and gold, never boldness. Italic
appears exactly once, on the colophon signoff.

### Hierarchy

- **Display** (400, clamp(3.3rem, 12.5vw, 10.8rem), lh 0.98, ls .045em,
  uppercase, Italiana): the landing hero name only. Carries the gold halo
  text-shadow (see Elevation) — except under
  `@supports (background-clip: text)`, where the name becomes **the
  sheen**: gradient-clipped starlight through which a narrow band of
  heated gold (with a trailing afterglow) sweeps left to right every 10s
  (`name-sheen`, linear, 2.6s delay; background-size 400%, rest position
  pure starlight). There the halo moves to drop-shadow filters
  (text-shadow paints over clipped text in WebKit), the shared `resolve`
  keyframes omit `filter` from their end state so the property is
  released after the entrance, and `.name:hover` ignites (brightness
  1.04 + heated-gold aura, .7s). Paint-only by law: the name's geometry
  never moves, so the pool's mirror stays true. Reduced motion and
  unsupporting browsers rest on solid starlight.
- **Headline** (400, clamp(3rem, 9vw, 7.5rem), lh 1.02, ls .05em, uppercase,
  Italiana): archive page titles (`.obs-title` — "The Meridian", chart names),
  same gold halo. Landing section titles (`.sect-title`) are the smaller
  variant: clamp(2.4rem, 6vw, 4.6rem), lh 1.05.
- **Title** (400, clamp(1.7rem, 3.6vw, 3rem), lh 1.08, ls .06em, uppercase,
  Italiana): station names on the meridian. The brand wordmark (1.35rem,
  ls .1em) and section numerals (1.3rem, ls .35em) are Italiana at label scale.
- **Body** (400, .74rem, lh 2.15, ls .13em, uppercase, Fragment Mono): reading
  copy — the bio, max-width 64ch, in Reading Cream. Root body text is 1rem/1.6
  Fragment Mono, but no shipped surface sets paragraphs at root size.
- **Label** (400, .56–.64rem, lh 1.7–1.9, uppercase, Fragment Mono): the log
  lines — nav, captions, data rows, counters, badges, legal. Tracking is the
  hierarchy within labels: .5em (descend cue), .4em (terminus), .34em (plate
  labels), .3em (data lines, counters, captions), .28em (nav), .26em (station
  data, collection captions), .24em (legal), .22em (video badge), .2em
  (signoff), .14em (lightbox note).

### Named Rules

**The Log-Line Rule.** All microcopy is Fragment Mono, weight 400, uppercase,
tracked ≥ .13em, at .56–.74rem. If a piece of text is not a designation
(Italiana) it is a log line — there is no third voice.

**The Recenter Rule.** Centered tracked-caps labels carry
`text-indent` equal to their `letter-spacing` (cue .5em, section numerals
.35em, seal .22em, terminus .4em) so the tracking's trailing space doesn't
push them off optical center.

**The Tabular-Instrument Rule.** Counters are zero-padded with
`font-variant-numeric: tabular-nums` ("Plate 01", "042 / 119"); charts and
sections are numbered in Roman numerals ("Chart II", section "I · The Plates").

## Layout

A full-bleed vertical descent — no boxed page container, no cards. Content
fields (atlas grid, meridian, masonry) cap at **1480px** centered; horizontal
padding is `--pad-x: clamp(1.25rem, 6vw, 6rem)` (the inner stylesheet's min is
1.2rem). Vertical rhythm is measured in sky, not pixels: section padding
`clamp(6rem, 15vh, 11rem)`, page tops `clamp(6.5rem, 15vh, 10rem)`, station
spacing `clamp(2.6rem, 7vh, 5.5rem)`, plate stacking `clamp(96px, 17vh,
230px)` — viewport-proportional clamps throughout.

- **Landing:** 100svh hero: the name stands on The Void's pool of black
  water (a canvas floor whose waterline sits at the name's baseline), under
  the orbit ring, with the descend cue pinned at the pool's far edge — no
  photograph shares the first viewport. Plates descend in a meandering
  single column (min(86vw, 640px), alternating flex-start/flex-end); at
  ≥900px every plate meanders in a 4-cycle of widths (37–64vw) and
  alignments. The Atlas becomes a 12-column grid with a repeating editorial
  cycle: first card full-width at 21/9, then 7/5-column splits, 1/1
  squares, and vh margin-top staggers.
- **Overture (/work):** the page opens on The Instrument — a full-bleed
  560vh runway (the `.page` padding-top moves onto `.obs-head` beneath it)
  whose sticky 100svh stage holds the drawing; The Meridian title follows
  as the visitor scrolls on.
- **Meridian (/work):** one center line, stations alternate right/left
  (`justify-content` flip on odd children), station link min(44%, 620px),
  plates at 3/2. At ≤760px the line moves to a left rail (12px), stations go
  full-width with 34px left padding, and the header left-aligns — the descent
  stays one continuous line.
- **Chart (/c/*):** CSS multi-column masonry — `columns: 3` → 2 (≤1024px) →
  1 (≤640px), gap `clamp(14px, 1.6vw, 24px)`; images keep real aspect via
  width/height attributes (no layout shift).
- **Breakpoints observed:** 560px (landing compaction), 640px (masonry 1-col,
  lightbox compact, collage stacks), 760px (meridian rail), 900px (landing
  desktop choreography, parallax), 1024px (masonry 2-col).
- **Z-ladder:** starfield 0 → void pool canvas 1 / content 1 → orbit ring 2 →
  helm 3 → topbar 40 → skip 200 → lightbox 1000–1002 (admin-side fixed
  chrome uses 920–960).
- Anchored sections carry `scroll-margin-top: 4.5rem` under the fixed topbar.

**The Sky-Rhythm Rule.** Vertical space between observations is proportional
to the viewport (vh-based clamps), never a fixed pixel scale — the descent
must feel like distance traveled.

## Elevation & Depth

There is no elevation. Nothing floats above anything on a shadow stack;
depth is darkness and light. `box-shadow` exists in exactly one role:
**emitted light** — zero-offset, gold/cream, blurred glows that make a plate
appear to spill light into the void.

### Shadow Vocabulary (all glows, never offsets)

- **Plate bloom** (`box-shadow: 0 0 34px rgba(240,230,205,.09), 0 0 110px
  20px rgba(212,175,55,.05), 0 0 240px 48px rgba(212,175,55,.028)` on an
  inset `::after`): the landing plate's ambient light, fading in over 2.6s
  after ignition. Stations use the two-layer variant (34px/.08 + 110px/.045).
- **Frame hover bloom** (`0 0 30px rgba(240,230,205,.1), 0 0 90px 14px
  rgba(212,175,55,.05)`): chart frames on hover only, .7s ease.
- **Lightbox frame glow** (`0 0 60px rgba(240,230,205,.07), 0 0 160px 30px
  rgba(212,175,55,.05)` on `inset 8% 6%`): the held plate's own light.
- **Title halo** (`text-shadow: 0 0 42px rgba(212,175,55,.22), 0 0 130px
  rgba(212,175,55,.1)`; archive titles use .18/.08): display headings glow
  faintly gold.
- **Ink glow** (`0 0 18px rgba(212,175,55,.35)`): the meridian ink. Lit
  station ticks glow `0 0 16px rgba(212,175,55,.55)`.

Depth layering: the starfield is a `position: fixed` sky the page scrolls
past (two ::before/::after layers of 1–1.5px radial-gradient stars, star-white
+ heated gold, opacity .30–.38, the gold layer twinkling over 9s); scrims are
vertical fades of the void itself (topbar gradients, lightbox backdrop
rgba(4,4,4,.985)). No backdrop-filter, no background-attachment — ever.

**The Bloom-Not-Shadow Rule.** `box-shadow` may only render light the element
emits: zero-offset, gold or cream, generously blurred. A dark or offset drop
shadow is a foreign object in this world.

## Shapes

Everything is sharp. `border-radius` does not appear in the public world —
photographs, buttons, badges, and overlays are all hard-cornered (`rounded:
none / 0px`). Photographs are never bordered, rounded, or masked.

Line work is hairline: 1px rules (seal rules, colophon border, underlines with
4–6px offsets), 1px outlines, the 1px meridian line. Drawn geometry is the
world's iconography: the orbit ring (dash-array'd gold circle with a single
star), the station tick (9px square rotated 45° — a survey mark, not a
bullet), the terminus reticle (one-stroke cross-and-diagonals with a filled
center), chevrons and arrows as bare 1.4px strokes.

**The Drawn-Icon Rule.** Icons are one-stroke inline SVG paths —
`fill="none" stroke="currentColor" stroke-width 1–1.4` — built in markup or by
`app.js`'s `icon()` helper. Never font glyphs, never emoji, never icon fonts.

## Components

### Topbar
- **Style:** fixed full-width, padding 1.05rem × clamp(1.1rem, 4vw, 3rem); a
  void scrim gradient (landing .92→0; archive .97 at 42% → .6 at 78% → 0,
  opaque through the brand's own band so giant titles scroll beneath legibly).
- **Brand:** "H·B" in Italiana 1.35rem, ls .1em, gold; middot in Gold Dim;
  hover Heated Gold (instant).
- **Nav:** label-voice links (.6rem, ls .28em) in Dim; hover and
  `[aria-current]` go Heated Gold with a Gold Dim underline at 6px offset.
  On the landing the topbar fades in at 2.3s, after the name resolves.

### The Void (hero pool canvas)
`<canvas class="void-water">` (z1, aria-hidden, pointer-events none), painted
by the landing's last script block; fades in 2.4s at .9s.
- **The pool:** a near-black floor (#0b0a08 at the waterline into the void)
  whose horizon sits at the name's baseline — the name stands ON the water.
  A faint gold halo pools under it; a resting hairline ellipse marks where
  it touches.
- **The reflection:** the name, sampled from an offscreen canvas render
  (canvas-measured so no name ever clips; ctx.filter blur with a five-pass
  offset fallback for Safari ≤ 17), drawn in 3px slices with a three-wave
  sway that grows with depth (one wave travels shoreward) and bands of
  light climbing through the alpha (envelope .26 × .8–1.1 shimmer),
  capped so it never runs under the cue. `.name` is nowrap so the pool
  mirrors it truly.
- **The wind:** nine bowed glint streaks (heated gold ≤ .055) drifting
  across the pool, breathing on 5–12s periods, wrapping off-canvas via a
  padded span so no seam ever shows.
- **The mirrored sky:** twenty-six starlight sparks (≤ .16, perspective-
  squashed ellipses) twinkling on 2.2–6.7s periods, adrift on a slow
  current, also wrapping through a padded span.
- **Ripples:** expanding perspective ellipses (heated gold, ≤ .15 alpha),
  ambient rain every 1.1–2.8s anywhere on the pool (12% heavy), a soft
  groundswell (life 6s, ≤ .07) every 9–15s, and on pointermove/pointerdown
  over the water (120ms throttle, passive listeners). Cap eviction spares
  `soft` groundswells so pointer play can't delete one mid-fade.
- **The bodies:** three dots orbiting the name's center (gold, starlight,
  monogram gold; periods 21/34/52s), nearer arc brighter, mirrored faintly
  in the pool while above the waterline — where each also lays a moonglade,
  a broken wobbling path of light down the water (≤ .05).
- **Breath:** the halo (8.5s period) and the resting ring (alpha and
  geometry, ~7–9s) inhale and exhale; every ambient layer is a pure
  function of t, so the reduced-motion still frame inherits them all.
- **Discipline:** pauses off-screen and in hidden tabs (both flags ANDed);
  a single still frame under reduced motion, with a change listener that
  halts or restarts the loop mid-session; DPR watched across displays.

### Section Header (logbook chapter — landing)
A 1px 44px plumb line fading down to gold → Roman numeral (Italiana 1.3rem,
ls .35em, gold) → section title (Italiana clamp) → mono subtitle in Dim 2.
Centered; revealed as one `.reveal` unit.

### The Instrument (the overture of /work)
`<section class="instrument">` (a 560vh runway, 480vh ≤760px) holding a
sticky 100svh `.instrument-stage`: a `<canvas>` painted by
`static/instrument.js`, a DOM label layer, the photograph figure, the head
("The Instrument" · Canon EOS · drawn in its own light), a log-line readout
(bottom-left, survey-mark bullet), the epoch caption, the "Look inside" cue
(the landing's descend cue as a button) and a hint line.
- **The drawing:** a reflex camera — EOS-class body with a 18–55 kit zoom —
  built in millimetres in `instrument.js` (EF flange 44 mm: mount face
  z = 18, sensor z = −26) and projected by a painter's-algorithm renderer.
  Sixteen labelled parts: front element, zoom barrel, iris (7 blades),
  rear group, lens mount, reflex mirror (+ sub-mirror), focusing screen,
  pentamirror, eyepiece, two-curtain shutter, APS-C CMOS sensor, main board,
  vari-angle LCD, mode dial, hot shoe, battery. Materials: the body and
  barrels are **ghost shells** (gold hairline edges, no fill); internals are
  near-void fills shaded by one light with gold feature edges; glass is
  starlight — faint fill, specular glint, rim rings; the sensor is gold and
  ignites. Feature edges only, never the triangulation; depth fog dims the
  far lines; parts the eye passes through fade.
- **The runway (scroll progress p):** assemble on load (time-based — parts
  arrive from a seeded scatter, staggered, ~2.5s; then an ambient yaw/
  float at rest) → **turn** 0–.22 (one full rotation from the grip-side
  3/4 view, yaw +34°, pitch 11°) → **explode** .22–.50 (parts separate
  along the optical axis; labels tethered by gold leader lines, staggered)
  → **return** .50–.60 and **swing** .51–.61 (the eye orbits round to the
  front at full distance — never through the body) → **dolly** .60–.67 down
  the axis to the front glass → **enter** .67–.86 (the visitor is the
  light: through the glass, the barrel rings tunnel past, the iris opens
  .70–.76 from f/3.5-ish to wide, the mirror lifts .75–.80, the first
  curtain drops .80–.845, nine gold rays converge .71–.87, the sensor
  ignites .82–.885) → **record** .88–.96 (the 3:2 photograph figure scales
  uniformly from the sensor's screen rect to cover the stage; the drawing
  dissolves .915–.985; the epoch caption arrives .95–1). The readout names
  each phase.
- **The photograph:** `config.INSTRUMENT_PHOTO_SHA1` (a gold moon,
  Cosmology, 2016 · Oct 17), bundled into `/img/` by the exporter; rests at
  brightness .7 on the sensor and reaches 1 as it fills (Only-Light).
- **Interaction:** drag turns (yaw ±, pitch clamped ±38°, decays back after
  release; weight fades out through the swing); `touch-action: pan-y
  pinch-zoom` so vertical touch still scrolls; "Look inside" tweens the
  scroll through the runway (~14s, smoothstep, `scroll-behavior` forced
  auto for the tween) and stops on wheel/touch/scroll-keys/drag.
- **Discipline:** canvas DPR ≤ 2 (1.5 coarse pointers), lower segment
  counts below 900px / coarse; pauses off-screen (IntersectionObserver;
  hidden tabs need no gate — rAF stops there and some embedded viewers lie
  about visibility); DOM writes are transform/opacity only, label widths
  measured once (and on `fonts.ready`), labels flip sides rather than run
  off the stage; chrome entrances are painted by the script (a CSS
  `animation` on opacity would override inline writes). Reduced motion:
  the runway unpins, one still of the exploded, labelled view at extra
  distance, the photograph and epoch shown plainly beneath; the cue and
  hint are removed. Without script the section does not exist and the
  Meridian begins at once.

### Observation Header (archive)
Centered `.obs-title` headline with halo; data rows beneath in label voice
("The archive in order of observation · 2008 — 2016"), values in gold `.au`
spans; second row dimmer (`.obs-data--dim`). On chart pages a return link
sits above: gold label text with a drawn 22×11 arrow that slides -4px on
hover (.45s ease-out).

### Plate (landing tile)
- Markup (server-owned): `<figure class="tile tile--N" data-speed="0.xx">`.
- A counter-generated label — "Plate 01" (.58rem, ls .34em, gold, top -2.2em)
  — annotates each; the ambient bloom `::after` fades in 2.6s after ignition.
- **Ignition:** unlit = `opacity: 0; transform: scale(.965); filter:
  brightness(.22) saturate(.7)` on the img; `.is-lit` (IntersectionObserver,
  threshold .12, rootMargin -6% bottom) eases it on over 1.3s ease-out.
  Every plate ignites on descent — none shares the hero viewport.
- **Hover:** brightness 1.06 with shortened .45–.55s recovery.
- **Parallax:** desktop fine-pointer only — `data-speed` drift, transform-only
  translate3d, ±60px clamp, rAF-throttled.

### Atlas Card (landing collection card)
Cover at 3/2 (grid cycle overrides to 21/9 and 1/1), resting at
brightness .9; hover/focus lifts to 1.02 and scales 1.028 over .9–1.4s.
Caption is a label line in Dim ("01 — Cosmology · 119") going Heated Gold on
hover. Cards ignite with a 110ms stagger (capped 440ms), rising 26px.

### Meridian Line + Ink
A 1px full-height rule in faded gold gradient; inside it the ink
(`gradient Gold Dim → Gold`, glow 18px) draws via `transform: scaleY()` from
`transform-origin: top` — set by `app.js` from scroll progress of the
viewport's lower third (`(vh · 0.72 − rect.top) / height`, clamped 0–1,
rAF-throttled). Reduced motion pins it fully drawn.

### Station (one collection observed)
`<li class="station">` = tick + link. The tick is the 9px rotated survey
mark (gold border, void fill); when its station is hovered it fills gold and
glows. The link holds the plate (3/2, brightness .88 → 1.03 + scale 1.022 on
hover/focus), the bloom, then name (Title voice, hover Heated Gold, .45s) and
data line ("Chart II · 36 frames · 2014 — 2015"). **Ignition:** link rises
28px from opacity 0 over 1.1s ease-out; tick fades in .9s with .2s delay;
`app.js` staggers reveals 45ms × (n mod 10).

### Terminus
Closes the meridian: the drawn reticle mark (22px, gold) over "First light"
(.58rem, ls .4em, Dim 2). Decorative, `aria-hidden`.

### Chart Frame (`.ph`)
Server-owned anchor with `data-sha1`, `data-taken`, `data-kind`. Masonry
item, `break-inside: avoid`. **Ignition:** ember state `opacity 0,
scale(.972), brightness(.25) saturate(.72)` → `.is-in` over 1.1s. **Hover:**
brightness 1.07 + hover bloom. Videos carry a "Video" badge — label voice
.56rem, gold on rgba(5,5,5,.72), 1px Gold Dim border, top-right.

### Lightbox (the viewing instrument)
Built entirely by `app.js`; `role="dialog" aria-modal="true"`.
- **Backdrop:** rgba(4,4,4,.985), fades .45s (`.is-open`); clicking the dark
  itself closes.
- **Counter:** fixed top-left, gold, tabular, zero-padded — "042 <span
  dim>/ 119</span>", `aria-live="polite"`.
- **Travel:** two alternating `<img>` layers. Classes: `.is-on` (visible),
  incoming `.from-next` (translateX(34px) scale(.99)) / `.from-prev`
  (-34px), outgoing `.to-next` (translateX(-26px), fade) / `.to-prev` (26px).
  Sequence: set src → force reflow (`void offsetWidth`, deliberately not rAF —
  rAF starves in throttled tabs) → remove `from-*`, add `.is-on`; outgoing
  swaps class and is unloaded after SWAP_MS = 560ms (matches the .55s CSS
  transition). Reduced motion: instant swap, no travel classes.
- **Frame:** max min(1440px, 86vw) × 78vh, contain-fit, arriving at
  scale(.985) → none; the frame glow sits behind it. Caption below in label
  voice — epoch only, in gold ("2016 · Mar 4"). Neighbors preload.
- **Controls:** drawn-icon buttons, gold → Heated Gold — close (18px ×,
  hover rotates 90°), chevrons (15×28, hover slide ±5px); 30%-wide invisible
  edge tap zones with `w-resize`/`e-resize` cursors; swipe (44px, axis-locked);
  ArrowLeft/Right; Escape; focus trapped across visible buttons, returned to
  the opener on close. Video frames swap in a note linking the original.
- **Focus inside:** 1px gold outline, offset 5px.

### Colophon
Top border rgba(212,175,55,.14); centered. Signoff — the one italic line,
gold: "The photographs are the only light." Then legal ("© year HARV BALU —
Bay Area, California") and coordinates ("37.5° N · 122.0° W") in Dim 2.
No links, no contact.

### Skip Link
Fixed top-center, hidden at -4rem until focused; void background, 1px gold
border, gold label text — the only bordered control in the world.

### Focus States
Landing: `1px solid gold, offset 5px`. Archive base: `2px solid starlight,
offset 3px` (inherited `--ink` rule); the lightbox restores the gold
treatment. Both are visible-by-default `:focus-visible` outlines on the void.

### Motion Summary (system-wide)
The Instrument (above) is the one scroll-scrubbed sequence in the world:
its progress is the runway's scroll fraction, its entrances are time-based
(assembly ~2.5s from first paint, chrome 1.5–3.7s), and its DOM writes are
transform/opacity only; the canvas itself is exempt from the property
contract but keeps the grammar — things resolve out of the dark, light
converges, the photograph is the brightest object.

Easing token `--ease-out: cubic-bezier(.19, .61, .26, 1)` everywhere.
Durations: ignition 1.1–1.3s; blooms 2.2–2.6s (delayed .25–.4s); hover
recoveries .45–.7s; lightbox travel .55s; twinkle 9s; orbit spin 150s.
Landing load choreography: name *resolves* (blur 20px + brightness 1.9 → clear,
1.7s at .5s) → the void's pool fades in (2.4s at .9s) → cue *rises* at 2.3s
alongside the topbar → the name's sheen begins its 10s passes at 2.6s. The pool canvas animates continuously (reflection sway with
light bands, wind glints, mirrored starlight, ambient rain + groundswells,
moonglades, breathing halo/ring, orbiting bodies) but pauses off-screen and
collapses to one still frame under reduced motion; the reduced-motion block zeroes animation-delay as well as
duration so every entrance lands at once. Scroll/entrance motion is transform/opacity/filter ONLY; the
archive additionally eases color/background/box-shadow on small hover chrome
(station tick and name, lightbox button color) at .3–.8s, while landing chrome
color swaps stay instant. `prefers-reduced-motion` collapses everything:
.01ms durations, all ignition states forced visible, parallax and ink
unbound in JS, lightbox swaps instant.

## Do's and Don'ts

### Do:
- **Do** set every public page on the void (#050505) with the fixed starfield
  behind content at z-index 0 — one sky, no second background color.
- **Do** let images rest dimmed (brightness .88–.9) and reach full light only
  through ignition, hover, or the lightbox (The Only-Light Rule).
- **Do** write all microcopy as Fragment Mono 400 uppercase, .56–.74rem,
  tracked ≥ .13em, and put data values in gold spans inside dim lines.
- **Do** animate entrances as ignition: opacity + scale(.96–.975) +
  brightness(.22–.25)/saturate(.7) → lit, over ~1.1–1.3s `--ease-out`, driven
  by IntersectionObserver, with blooms fading in after.
- **Do** draw every icon as a one-stroke SVG (`stroke-width` 1–1.4,
  `currentColor`, no fill) and every counter zero-padded tabular; number
  charts and sections in Roman numerals.
- **Do** provide the static promise: reduced-motion must neutralize both the
  CSS (durations, forced-visible states) and the JS branch (no parallax, no
  ink, instant lightbox swap).
- **Do** preserve `string.Template` `$var` placeholders and server-owned
  component markup (`.tile`, `.collection-card`, `.station`, `.ph`) — restyle
  them, never restructure them in CSS-only changes.
- **Do** caption photographs with their epoch only ("2016 · Mar 4" /
  "2008 — 2016").

### Don't:
- **Don't** use `backdrop-filter` or `background-attachment` anywhere, or
  animate layout properties — scroll/entrance motion touches only
  transform/opacity/filter.
- **Don't** cast dark or offset drop shadows, round a corner, or border a
  photograph — shadows are zero-offset light blooms only.
- **Don't** show filenames, titles, EXIF, or any metadata beyond the epoch;
  don't add contact information (email, phone, social) anywhere public.
- **Don't** introduce a third typeface, a second font weight, pure #FFFFFF
  text, or gold body paragraphs.
- **Don't** use font glyphs, emoji, or icon fonts for iconography.
- **Don't** apply the cream `:root` system (Anton, paper, ink) to any public
  surface, or Observatory styling to `body.admin` — the boundary is the
  `body.inner` scope.
- **Don't** default to a uniform same-size card grid; new fields follow the
  world's asymmetric grammars (meander, meridian, editorial cycle, masonry).
