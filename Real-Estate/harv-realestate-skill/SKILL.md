---
name: harv-realestate
description: "Harv Balu's wrapper around Zubair's AI real estate skill bundle. Enforces MLS/RPR-first comp data, Fair Housing compliance (federal FHA + California FEHA), per-buyer config from CLIENT.md frontmatter, and Telegram notifications via Hermes bot. Use when running real estate property analysis for Harv's clients (buyer-first in v1; seller in Phase 2). Subcommands: quick / analyze / compare / email."
---

# Harv Realestate Skill

Harv-specific orchestrator wrapping Zubair's AI real estate skill bundle.

## When to use

Use this skill (NOT Zubair's `realestate` directly) when:
- Running property analysis for one of Harv's actual clients (buyer or — Phase 2 — seller)
- The client has a CLIENT.md in `Real-Estate/Residential/Buyers/` or `Sellers/` with frontmatter
- Output may need to flow to a client (FHA + FEHA compliance scrub is mandatory)

Use Zubair's `realestate` directly (without this wrapper) when:
- Quick speculation or speculative property research with no client attached
- Investor-pure analysis where buyer-context doesn't apply

## Subcommands

### `quick ADDR --client=<folder>`
Fast 60s screen using `realestate-quick`. Auto-PRELIMINARY (web-only). Lot-size flag rendered if `lot_threshold_sqft` set in CLIENT.md. Telegram notification optional. Output: REPORT.md + MARKER.md in property subfolder.

### `analyze ADDR --client=<folder>`
Full 2-3min analysis using `realestate-analyze` (5 parallel agents). Phase 0 asks for MLS/RPR PDFs. Lot-size flag, Fair Housing scrub, output marker, Telegram notification. Output: REPORT.md + MARKER.md.

### `compare ADDR1 ADDR2 [...] --client=<folder>`
Side-by-side using `realestate-compare`. Phase 0 per-address. Output: COMPARE.md at parent compare folder.

### `email <client>`
Wraps `harv-email-drafter`. Reads most recent REPORT.md from `<buyer-folder>/<property-folder>/`. Drafts client-voiced email. Runs Fair Housing scrub on email body. Writes EMAIL-DRAFT.md.

## Workflow (analyze case — canonical)

1. **Bootstrap.** Read CLIENT.md frontmatter via `scripts/load_buyer_config.py`.
2. **Property subfolder.** Resolve or scaffold `<buyer-folder>/<address>/`. Prompt for MLS/RPR PDFs if missing.
3. **Phase 0.** Set mode = verified or preliminary based on PDF presence.
4. **Underlying invocation.** Call Zubair's `realestate-analyze` with the address.
5. **Lot flag.** Run `scripts/render_lot_flag.py`; insert flag into REPORT.md.
6. **Fair Housing scrub.** Run `scripts/fair_housing_scrub.py`. On block, write VIOLATIONS.md, exit non-zero, do not notify.
7. **Output marker.** Run `scripts/write_output_marker.py`; inject verification stamp at top of REPORT.md.
8. **Telegram.** Run `scripts/notify_telegram.py` (non-fatal on failure).
9. **Return.** File paths to user.

## Hard rules (read these — they are non-negotiable)

- **MLS/RPR-first.** Never fabricate. Web data is preliminary; always carries the marker.
- **Fair Housing.** No protected-class language ever. Defense-in-depth at agent prompt + post-scrub.
- **Output marker mandatory.** Every REPORT.md gets a stamp — verified or preliminary.
- **Email is separate.** Don't auto-draft. User invokes `email` subcommand explicitly.
- **Lot flag is informational.** Don't filter listings out — flag them for Harv's eye.

## Examples

```
/harv-realestate quick "5678 Oak Ave Hayward" --client=PinkyHayward-Union-City-May2026
/harv-realestate analyze "1234 Main St Hayward" --client=PinkyHayward-Union-City-May2026
/harv-realestate compare "1234 Main St Hayward" "5678 Oak Ave Union City" --client=PinkyHayward-Union-City-May2026
/harv-realestate email PinkyHayward-Union-City-May2026
```

## CLIENT.md frontmatter schema

See `templates/buyer-config-schema.yaml` for full reference.

Minimal required fields: `client_name`, `client_role`. Everything else optional (defaults: empty lists, no thresholds, no flags).

## Reference

- Design doc: `Real-Estate/docs/plans/2026-05-09-realestate-skill-integration-design.md`
- Implementation plan: `Real-Estate/docs/plans/2026-05-09-realestate-skill-integration-plan.md`
- Underlying: Zubair's bundle at `Real-Estate/realestate-skills-Zubair-Trabzada/` (with Harv patches)
- Memory: `feedback-fair-housing-compliance.md`, `project-realestate-skill-integration.md`
- Hermes Telegram: `~/.hermes/.env` on n8n VPS, chat ID 5883909804
