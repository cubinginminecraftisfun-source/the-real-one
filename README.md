# 미용실 예약 · V2 mobile calendar update

**Already running V1? Read [UPGRADE_V2.md](UPGRADE_V2.md) first. Use `supabase/migrate_v2.sql` ONCE on your existing database. Never rerun setup.sql on an existing project.**

This is an update of the original Streamlit/Supabase app, not a different service: it reuses the server-side `salon/db.py` adapter, `salon_api` RPC, existing tables, passwords, bookings, rules and prices. The old time-button presentation has been replaced by a local custom calendar component inside Streamlit. V1 source/reference instructions are in archive/.

## UI and behavior

- Korean, high-contrast light interface inspired by the day-view layout of your supplied Google Calendar references; not a pixel-identical Google product or Google Calendar integration.
- Fixed toolbar and day heading; independent 24-hour timeline scroll area.
- Centered day arrows; horizontal day swipes with a direction threshold to separate them from vertical scrolling.
- 예약 button opens a seven-column weekly booking panel. Customers see occupancy; Dad also sees names.
- Tap a blank time or plus: initial 30-minute blue selection; drag either handle in 5-minute increments. Minimum duration 5 minutes, no crossing midnight; 24:00 is allowed as the end.
- Bottom sheet expands/minimizes; manual start/end input, service selection, name, comment, save. Dad gets availability and repeat controls instead.
- Customer top-right short code + eye; phone + copy, and current-day price icon. Dad gets password and price editing icons instead. No in-app QR.
- Daily/weekly repetition, inclusive end date or no end date for availability AND prices. Saving WITHOUT repeat affects only the chosen date. Date-specific rules take precedence over repeating rules; newest wins among rules of equal type.
- Red X on every app modal and bottom sheet. Floating success (green), warning (amber), error (red) messages disappear after about 3 seconds. Required privacy consent remains in the booking editor; decorative explanation captions were removed.
- Customer two-character A–Z/0–9 code only, valid 24 hours. No PIN. Code recovery moves access to the new browser session without extending expiry. Expiry does not cancel a booking; customers must contact the shop afterward.
- Administrator password initially 1111 only for a fresh install; upgrades preserve the existing password. No forced change. Key icon offers voluntary change; a new password must be 8–64 characters.
- Default opening hours remain 10:00–20:00, but the grid shows the whole day. Dad can set available/unavailable/tentative overrides anywhere within 24 hours. Reservations are limited to 90 days ahead.
- No customer accounts, payments, SMS/Kakao alerts or automatic pending expiry. Pending bookings hold the time until Dad decides.
- Every five-minute segment and interval overlap is checked on the server. Database exclusion constraint is a second overlap safeguard. Single hairdresser/chair.
- Open, connected pages refresh about every 10 seconds. This is polling, not Supabase Realtime push. Sleeping tabs may refresh later. Forms stay in the frontend while polling; price is revalidated at save.

**Security warning:** code-only recovery was requested for convenience. 1,296 combinations are not strong authentication: guessing a valid code gives access to that customer's reservation data/actions. Rate limits remain. Never place medical/sensitive details in comments. Change the public default admin password even though not forced.

## Fresh installation ONLY

Existing installations must use UPGRADE_V2.md instead of these steps.

1. Create GitHub, Supabase and Streamlit Community Cloud accounts. GitHub stores files; Streamlit runs Python; Supabase stores data. GitHub Pages cannot run this app.
2. Create a NEW Supabase project. Save the database password privately; the app does not use that password. Choose a region appropriate for your customers.
3. In SQL Editor run ALL of `supabase/setup.sql` ONCE. The final two privilege checks must be false. Do not expose salon_private through the Data API; keep public available for the server function. Do not add permissive anonymous policies.
4. Enable Cron/pg_cron in the Supabase dashboard. Run `supabase/retention.sql` ONCE. Confirm salon-daily-retention is active. It runs at 03:10 Korea time and deletes appointments more than 30 days old at the next run. Check actual job results. Review the privacy notice, hosting and provider backup retention before real customers use it.
5. Get the project's HTTPS URL and server-side Secret key starting sb_secret_ from project API settings. Never use the anon/publishable key here. Never upload real keys to GitHub.
6. Extract the project and upload the CONTENTS of hae_salon to GitHub, preserving folders. app.py and requirements.txt must be at repo root. Include .streamlit/config.toml and the SAFE secrets.toml.example, but never an actual secrets.toml. Include the entire salon/calendar_frontend folder.
7. In Streamlit Community Cloud connect that repo, branch main, main path app.py. Use Python 3.12 if offered. Paste the configuration below into Streamlit app settings → Secrets, not a repository file.

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REFERENCE.supabase.co"
SUPABASE_SECRET_KEY = "API KEY HERE - your real sb_secret_ key"
AUTH_PEPPER = "API KEY HERE - your own 64-character random server secret"
SHOP_NAME = "아버지 미용실"
SHOP_ADDRESS = "실제 매장 주소와 층수"
SHOP_PHONE = "02-000-0000"
```

Generate AUTH_PEPPER privately with a trusted password manager, or run on your own computer:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Use the generated 64 characters, not the command. Do not reuse the admin password. Alternative legacy key: omit SUPABASE_SECRET_KEY and use SUPABASE_SERVICE_ROLE_KEY with a service_role JWT. Choose one. Credentials are read only by salon/db.py; the iframe does NOT receive them or authentication tokens. All relevant placeholders in .streamlit/secrets.toml.example are marked API KEY HERE.

8. Deploy and open the HTTPS app. Permit customer access without requiring your personal Streamlit sign-in; test incognito. Log into admin using 1111, set actual opening/closed times and prices. Change password through the key icon if desired.
9. Run the live checks in TESTING.md on a test deployment before accepting bookings. Optional `supabase/verify.sql` is a rollback-only smoke test for a NEW EMPTY TEST database with default password/menu. Never run it against live customer data. It was syntax-checked but not executed against your account.
10. Share the app URL or make a static QR with your usual trusted QR/printing tool. There is deliberately no QR feature inside this revision. Keeping the same URL means already printed QR codes keep working.

No new paid API is required. No npm build is required for Streamlit deployment; frontend assets are included. package.json is only for optional offline JavaScript tests.

## Development checks

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python tools/check_sql_syntax.py
npm install --ignore-scripts --no-package-lock
npm test
```

Frontend tests use a simulated DOM, NOT a browser renderer. Native touch scrolling, viewport/soft keyboard, clipboard restrictions and Streamlit iframe sizing require real-device acceptance testing. No claim of exact screenshot fidelity, live deployment validation, database execution or security audit is made.

## Files

- app.py: Streamlit wrapper and secret configuration check.
- salon/db.py: original server-side Supabase adapter.
- salon/mobile.py: event handling and explicitly filtered view data.
- salon/calendar_component.py + salon/calendar_frontend/: local interactive calendar, no CDN/build step.
- supabase/migrate_v2.sql: existing V1 → V2 migration.
- supabase/setup.sql: fresh V2 only.
- supabase/retention.sql: existing daily retention job definition (do not schedule twice).
- supabase/verify.sql: fresh empty TEST project only; rolls back.
- archive/: historical V1 references, not active modules.
- tests/, tools/check_sql_syntax.py: offline checks.
- UPGRADE_V2.md: deployment steps for an existing installation.

## Troubleshooting

- Blank component: verify index.html, app.js, style.css were uploaded under salon/calendar_frontend; reboot Streamlit and reload the phone page. Missing secrets are reported on the Streamlit setup screen.
- HTTP errors after updating Python files: check that migrate_v2.sql completed on the SAME Supabase project named in Streamlit Secrets. Never solve this by exposing private tables.
- Existing-table/constraint error: migration may already be applied or setup.sql was used incorrectly. Run ROLLBACK; and stop; do not delete data. Share the error with keys removed.
- Copy button blocked by browser: long-press the displayed phone number to copy; phone link still opens the dialer.
- Login expired: log in again with an active code or admin password. Expired customer codes cannot recover old reservations; phone the shop.
- Form save times out: inspect bookings first. Writes are not automatically retried because the database might have committed before the response was lost.
- There are no app data backups in this ZIP. Use your provider's actual backup/export and restore capabilities; free-plan availability/uptime is not assumed.
