# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Visitors Harv Balu sends to the site — clients, friends, fellow photographers —
plus anyone landing on harvbalu.net. They come to *look*, not to hire or buy:
the site is "a display of my artwork" (Harv, 2026-08-05). No lead capture, no
contact routes, by explicit instruction.

## Product Purpose

A public gallery of Harv Balu's photography, kept strictly separate from his
realtor identity. Success = a visitor browses collections and individual
frames and comes away with the sense of a serious photographic practice.
[Inferred from session directives; not interviewed.]

## Operating Context

- Static site on Vercel (harvbalu.net) built by `export_static.py` from the
  private portfolio app's SQLite DB + templates. No server at runtime.
- Grid/lightbox images embed from a home-hosted WordPress (~90% uptime);
  the landing's images are bundled into the deploy so the first viewport
  never depends on the home server.
- Curation happens in the private admin app; the DB's `visibility` flags are
  the source of truth for what is public.

## Capabilities and Constraints

- 240 public camera photographs in 6 collections (Cosmology 119 — verified
  Canon EXIF, Monterey Bay Aquarium 36, Cancún 35, Niagara Falls 32,
  New York City 14, Alviso Marina 4). Dates span 2008–2016+.
- The "AI Generated" collection (210 images) is EXCLUDED from the public site
  for now — camera work only (Harv, 2026-08-05: "we'll come back to this").
  Exclusion lives in the exporter, not the DB, so his admin curation is intact.
- Thumbs are 400px, display derivatives 1600px, sha1-addressed. No originals
  ever ship.
- No contact info anywhere: no email, phone, or social links. Footer carries
  only name + © + "Bay Area, California".
- Photos carry no titles or filenames publicly — date (epoch) only.
- Stack: vanilla HTML/CSS/JS, no frameworks, no build step beyond the
  Python exporter. Templates are shared with the live private server
  (string.Template `$var` placeholders must be preserved).

## Brand Commitments

- Identity: "HARV BALU" (H·B monogram), fully separate from HarvRealtor.
- The "Observatory" visual world is the committed, user-approved identity
  (won a 3-judge panel 2026-07-30): #050505 void, warm star-white #F2EDE0,
  gold #D4AF37 instrument markings, Italiana display × Fragment Mono log
  voice, starfield, numbered plates, ignition reveals.
- Motion contract: no background-attachment, no backdrop-filter; animate only
  transform/opacity/filter; prefers-reduced-motion collapses to static.
- Voice: observatory/log-book register ("observations", "plates", "atlas",
  "field notes"), uppercase tracked mono microcopy.

## Evidence on Hand

- 240 real photographs with EXIF (the entire content of the site).
- `templates/` + `static/landing.css` embody the approved world.
- No testimonials, no press, no client list — and none may be invented.

## Product Principles

1. The photographs are the only light — interface recedes, frames lead.
2. Private by default; the public site is a curated window, never the archive.
3. One source of truth — static pages render through the same templates and
   queries as the live app; no second copy of markup to drift.
4. The front door must survive the home server being off.
5. Separate identity, no cross-contamination with realtor accounts or brand.

## Accessibility & Inclusion

Keyboard-completable lightbox, visible focus states, reduced-motion support,
AA-contrast microcopy on the void. [Standing practice in the codebase;
no user-stated requirement beyond it.]
