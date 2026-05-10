---
name: harv-showcase
description: "Branded client outreach: property roundup emails, nurture emails (holiday/check-in/info-share), and property landing pages. Gold/black HarvRealtor.com brand. Works on Mac and VPS. Trigger: 'showcase email', 'property email to [client]', 'landing page for [address]', 'holiday email to [client]', 'check in with [client]', or /harv-showcase."
---

# harv-showcase

Branded client outreach skill for Harv Balu / HarvRealtor.com. Three capabilities: property roundup emails, client nurture emails, and property landing pages. All output uses Harv's gold/black brand identity.

## Routing

Detect which capability the user wants from their request:

**Section A - Property Roundup Email:** Keywords like "property email", "listing email", "roundup", "houses to browse", or listing URLs present.

**Section B - Client Nurture Email:** Keywords like "holiday", "check in", "checking in", "happy", "season", "info share", "market update".

**Section C - Landing Page:** Keywords like "landing page", "property page", "create a page".

If ambiguous, ask the user which capability they want.

---

## Section A: Property Roundup Email

### Steps

**A1.** Collect recipient name and email address. Ask if not provided.

**A2.** Collect listing URLs (HarvRealtor.com or other) or offline property data.

**A3.** For each online URL: `WebFetch` the listing page. Parse from the HTML:
- Address (from `<title>` or `og:title`)
- Price
- Beds, baths, sqft, lot size
- Property type
- Description (from meta description or page body)
- Hero image URL (from `og:image` or first listing `<img>`)

**A4.** For offline properties: user provides address, price, beds, baths, sqft, lot, type, description, photo URLs. If no listing URL exists, ask if user wants a landing page generated (jump to Section C, then return with URL).

**A5.** Sort all properties by price ascending (default; user can override).

**A6.** Read the template:
```
~/.claude/skills/harv-showcase/templates/email-property-roundup.html
```

**A7.** Fill template placeholders:
- `{{CITY_NAME}}` - detected city (e.g. "Union City")
- `{{DATE}}` - today's date formatted as "May 10, 2026"
- `{{RECIPIENT_NAME}}` - client first name
- `{{INTRO_TEXT}}` - warm intro paragraph (see Voice Rules below)
- `{{SIGNOFF_TEXT}}` - e.g. "Talk soon,"
- For each property, duplicate the `<!-- PROPERTY_CARD_START -->` to `<!-- PROPERTY_CARD_END -->` block and fill:
  - `{{PROP_URL}}` - listing URL
  - `{{PROP_IMG}}` - hero image URL
  - `{{PROP_ALT}}` - image alt text (address)
  - `{{PROP_ADDRESS}}` - full street address
  - `{{PROP_PRICE}}` - formatted price (e.g. "$1,299,888")
  - `{{PROP_DETAILS}}` - beds/baths/sqft with middle-dot separators
  - `{{PROP_DESCRIPTION}}` - 2-3 sentence description

**A8.** Write the intro paragraph in Harv's voice. Mention number of homes, city, budget range if known. Tell them to reply with addresses they want to see in person.

**A9.** Save the filled HTML to a temp file, then create an Outlook draft:
```bash
python3 ~/.claude/skills/harv-showcase/scripts/create_outlook_draft.py \
  --subject "{{CITY_NAME}} Homes for You" \
  --to-name "{{RECIPIENT_NAME}}" \
  --to-email "{{TO_EMAIL}}" \
  --html-file /tmp/showcase-email-body.html
```
Fallback: use Graph API curl directly if the script fails. Token at `/tmp/ms365-token.json` or `~/.claude/ms365-token.json`.

**A10.** Report draft created. Remind user to review in Outlook before sending.

---

## Section B: Client Nurture Email

### Steps

**B1.** Detect email subtype from the user's request:
- **Holiday** - seasonal greeting (Thanksgiving, New Year, Diwali, etc.)
- **Check-in** - "thinking of you", touching base with a past client
- **Info-share** - forwarding useful info (rate changes, neighborhood news, new listings alert)

**B2.** Collect recipient name and email address. Ask if not provided.

**B3.** Pull any client context from conversation or memory: search criteria, last interaction, property interests, personal details (kids, job, hobbies).

**B4.** Read the template:
```
~/.claude/skills/harv-showcase/templates/email-nurture.html
```

**B5.** Generate body copy in Harv's voice (see Voice Rules below):
- Holiday: warm, seasonal, brief (3-5 sentences). Genuine, not generic.
- Check-in: reference last interaction if known, market conditions optional (2-4 sentences).
- Info-share: lead with the useful info, add context, CTA to discuss.

**B6.** Fill template placeholders:
- `{{EMAIL_TYPE_LABEL}}` - e.g. "Holiday Greetings", "Checking In", "Market Update"
- `{{DATE}}` - today's date
- `{{RECIPIENT_NAME}}` - client first name
- `{{BODY_CONTENT}}` - Claude-generated HTML paragraphs
- `{{SIGNOFF_TEXT}}` - "Warm regards," for holiday, "Talk soon," for check-in/info

**B7.** Save filled HTML to temp file, create Outlook draft via the helper script.

**B8.** Report draft created. Remind user to review before sending.

---

## Section C: Landing Page

### Steps

**C1.** Collect property data. If RPR PDF provided, extract: address, price, beds, baths, sqft, lot, year built, type, agent remarks, MLS#. If manual, ask for each field.

**C2.** Collect photo URLs: hero image + 3-8 gallery images.

**C3.** Collect listing URL if online (for canonical link + "View Details" CTA). If offline, the landing page URL becomes the canonical.

**C4.** Read the template:
```
~/.claude/skills/harv-showcase/templates/landing-page.html
```

**C5.** Fill template with all property data:
- Write a "Rare Find" custom summary (2-3 sentences, Harv's voice)
- Generate 4 property highlights based on the listing data
- Auto-populate payment calculator with list price

**C6.** Detect environment and save:
- **Mac:** `~/Library/CloudStorage/OneDrive-Personal/Web/HarvRealtor/LandingPages/{{ADDRESS_SLUG}}/index.html`
- **VPS:** `~/workspaces/showcase-output/{{ADDRESS_SLUG}}/index.html`

Environment detection: check if `/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/` exists. If yes, Mac. If no, VPS.

**C7.** Report file saved with full path. Remind user to deploy to HarvRealtor.net if needed.

---

## Voice Rules

These rules apply to ALL generated copy (emails, landing page summaries, intros, sign-offs).

- First person "I" (not "we" unless referring to the team)
- Use contractions: it's, I'm, we're, you're, I've, don't, won't, I'll
- **NEVER use:** "I hope this email finds you well", "per my last email", "please be advised", "as per", "moving forward", "circle back", "touch base", "leverage", "synergy"
- **No em-dashes or en-dashes** anywhere in copy. Hyphens in compound words are fine.
- No emoji in emails
- Greeting: "Hi [Name]," (familiar clients) or "Hello [Name]," (new/formal)
- Closing: "Talk soon," or "Warm regards," then "Harv"
- Always tell the client what happens next
- Keep it warm and genuine, not robotic

---

## Brand Rules

### Header
Always "HarvRealtor.com" in gold on ink-black background. NEVER "Realty Experts" in the header.

### Footer
```
Harv Balu, REALTOR | GRI, CIPS, PSA, FTBS
Realty Experts | DRE# 02195792
510-600-3425 | homes@HarvRealtor.com | HarvRealtor.com
```
All footer hyperlinks MUST use explicit `<a style="color:#FFFFFF; text-decoration:none">` to prevent email clients forcing blue.

### Color Palette
| Token | Hex | Use |
|---|---|---|
| Ink Black | `#0d0c0a` | Header/footer background |
| Gold | `#D4AF37` | Brand name, CTA buttons, accents |
| Gold Dark | `#A8861E` | Prices, gold text on white |
| Gold Soft | `#c9a44b` | Footer detail text |
| White | `#FFFFFF` | Footer links, body bg |
| Ink | `#2D2D2D` | Body text |
| Cream | `#f3efe6` | Outer email background |
| Border | `#e8e2d3` | Card borders |

### Typography
- Display: Playfair Display (Georgia fallback)
- Body: Inter (system-ui, Arial fallback)

### Contact Info
- Email: homes@HarvRealtor.com
- Phone: 510-600-3425 (work)
- Website: HarvRealtor.com

---

## VPS Portability Notes

If `/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/` does not exist, you are on the VPS.

- Landing pages save to `~/workspaces/showcase-output/` on VPS
- Outlook draft creation uses Graph API curl (same procedure both environments)
- Token at `/tmp/ms365-token.json` or `~/.claude/ms365-token.json`. If expired, follow the standard MSAL refresh procedure from `ms365-session-login-procedure.md`.
- Voice rules and brand tokens are embedded above (no external file dependency)
