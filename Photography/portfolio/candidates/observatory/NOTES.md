# OBSERVATORY — candidate notes

**Concept:** A pitch-black night observatory where the photographs are the only light —
numbered plates hanging in a starfield void, catalogued in a gold-ruled logbook.

**The one thing a visitor remembers:** his photos glowed like celestial bodies —
each one ignites out of darkness with a warm bloom as you descend.

**Type:** Italiana (hairline high-contrast display — the name reads as light filaments)
× Fragment Mono (observatory-log voice: labels, coordinates, captions).
**Palette:** void #050505 · starlight #F2EDE0 · gold #D4AF37 / #EED688 (monogram echo)
· dim #A39C8B / #8A8375 · hairline rgba(212,175,55,.22). All text AA on void.

**Motion story:** Load — stars fade up, a dashed gold orbit ring (with one transiting
planet dot) fades in, HARV BALU resolves from blur/overbright, sub-lines rise, then the
three newest artworks flare in sequence around the name (JS-staggered 1.5/2.05/2.55s).
Scroll — plates 04–14 ignite ember→full (opacity+filter) via IntersectionObserver, each
with a CSS-counter "PLATE NN" label and an opacity-faded box-shadow bloom; rAF parallax
drift (transform-only, cached bases, fine pointers ≥900px). Hover — plates flare +1.06
brightness; instant gold color swaps (no color transitions — instrument-panel crisp).

**Mobile (375px):** hero becomes pure typography inside the ring arc; all 14 plates
join one meandering column; atlas stacks; verified no horizontal scroll at 375/1280/1440.

**Risks:** Italiana hairlines need ~3rem+ (held via clamps); glow shadows are static
pseudos (opacity-only animation) so compositor-safe; absolute hero plates anchor to
`main` — keep `.survey` unpositioned; server order change would re-cast the hero trio.
