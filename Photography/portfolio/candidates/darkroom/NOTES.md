# THE DARKROOM — candidate notes

**Concept:** The landing page IS Harv's working darkroom — a warm near-black room under
an amber safelight where a 35mm reel of his newest frames drifts by and every photograph
develops from black as you reach it.

**The one thing a visitor remembers:** prints *developing* — images enter black, pass
through an amber half-tone, and arrive fully fixed (filter transition, 1.8s).

**Type:** Big Shoulders (condensed industrial caps) + Fragment Mono (rebate captions,
spec sheets). **Palette:** room `#100D0B` · film `#1B1410` · paper `#F0E8D9` · dim
`#A89B87` · safelight amber `#E8A33D`/`#F6C56B` · monogram gold `#D4AF37` ·
china-marker red `#D9432F` (lamp dot + grease circles only).

**Motion:** load → safelight breathes, hero rises, reel frames switch on staggered,
belt drifts (JS clones the track for a seamless loop; pauses on hover); scroll →
sheets develop-in via IntersectionObserver; hover → pinned sheets straighten, crop
marks brighten, a red grease-pencil ellipse circles the caption, covers brighten.

**Mobile 375:** single-line hero title, strip stays a swipeable film, sheets stack
one-per-row with softened tilt, lamp label collapses to its red dot; zero x-overflow.

**Risks:** Big Shoulders axis URL (validated 200, both families); filter transitions on
7 covers (compositor-only, verified); marquee needs JS — no-JS gives a static scrollable
strip, reduced-motion kills drift and pre-develops everything.
