# V2 verification status and acceptance checklist

## Checks actually executed for this delivery

- 61 Python tests passed (calendar/core compatibility, API adapter, intent handling, token/ownership stripping, code-only login, optional password gate, replay protection and Streamlit wrapper smoke checks).
- 14 JavaScript simulated-DOM tests passed (24h grid/seven columns, code hide/show, 5-minute selection and initial duration, bottom-sheet collapse, time parser, price snapshot, admin icons/repeat controls, rule priority, toast timer/styles occupied-block labels, direction-locked synthetic swipe events and resize-handle events).
- JavaScript syntax checked with Node.
- setup.sql AND migrate_v2.sql parsed as SQL and their salon_api function bodies parsed as PL/pgSQL; retention.sql and verify.sql also syntax checked.
- Final ZIP is integrity-checked and contains frontend assets and upgrade instructions; no real secret file included.

## NOT verified here

No live Supabase project or production customer data was accessed. No database migration, SQL smoke script, concurrency/load test or actual deployed Streamlit/browser touch test was executed. DOM tests do not render pixels or emulate native touch scrolling/soft keyboards. No security audit or guarantee of pixel-identical Google Calendar UI is claimed.

## Required live acceptance, before real customers

Use a backed-up copy/test deployment, then follow UPGRADE_V2.md for your actual app.

- Existing reservations, names, comments, prices, recurring schedule and existing admin password remain after migration. Previous bookings gain 30-minute end times.
- Two-character recovery works with no PIN; original expiry is unchanged and the previous device is invalidated.
- No forced password change. Key icon opens optional password change; validate current password and matching new passwords.
- 320/360/390px phone widths and tablet: header remains readable, no toolbar overlap, timeline alone scrolls.
- iPhone Safari and Android Chrome: vertical scrolling never changes day, deliberate horizontal swipe changes one day. Arrow fallback works. Dragging resize handles does not navigate.
- Blank tap/plus creates a 30-minute range; drag both handles, auto-scroll near edges, manually enter 5-minute times; expand/minimize/close bottom editor. Check soft keyboard and orientation changes.
- Reserve 10:05–10:50, attempt 10:35–11:00 from another customer; overlap must fail. Simultaneous device submissions must not both succeed. Adjacent 10:50 start should succeed if available.
- Selected interval containing ANY unavailable segment fails; tentative segment results in pending. Outside default opening hours fails unless Dad explicitly marks available. End 24:00 allowed only for that day.
- Dad sees names/comments; another customer never sees them in day grid, weekly panel or API view data.
- Weekly/daily rules and prices honor inclusive end date/no end date. A single-day exception does not alter future occurrences. Delete repeat requires confirmation and affects the whole repeat.
- Prices always prefix ₩. Price changes during an open draft are rejected at save for review instead of silently charging the changed price.
- Pending approvals/rejections, own cancellation, Dad cancellation, no automatic cancellation by new unavailable rules.
- Phone copy works in HTTPS browser or provides long-press fallback. Every app popup has a clear red X.
- Success/warning/error messages float and disappear after ~3 seconds; forms retain entries after validation errors.
- A second device sees updates after ~10s while connected. After timeout, inspect existing bookings before retrying a write.
- Cron retention job still active and scheduled only once; actual run succeeds. Privacy/contact/retention notice is appropriate for the shop.

If a check fails, stop accepting bookings and record the error without secrets. Do not repeatedly rerun migration/setup or drop existing tables.
