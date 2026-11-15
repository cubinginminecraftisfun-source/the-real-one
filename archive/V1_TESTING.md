# Verification and live acceptance checklist

## Verified locally for this delivery

- 43 automated tests passed using pytest and Streamlit AppTest.
- Pure date/time logic: Korea timezone, week boundaries, default availability, rule ranges, one-date precedence, most-recent rule priority, existing-booking precedence, and past slots.
- Menu validation and read-only week HTML: calendar output does not include sample customer name/comment.
- Server request construction, client-identifier hashing, expiry cleanup, error redaction, no automatic retry after a failed network response, server-key headers, URL validation.
- Customer day/week switching, code show/hide, booking dialog submission, price/date flow.
- Admin forced initial-password screen, schedule dialog, recurring rule save, last-slot handling, plus-button price row creation/edit/save.
- Source check rejects radio/selectbox/multiselect/expander/select-slider use in app.py.
- setup.sql (including PL/pgSQL function), retention.sql, and verify.sql parsed with pglast. Parsing is not execution.
- ZIP contents checked, with no real secrets.toml, credentials, caches, or virtual environment bundled.

All database API responses in the UI tests are **mocked**. These tests do not establish real Supabase connectivity, public-role privileges on your account, real simultaneous request behavior, hosted uptime, browser rendering fidelity, or Cron execution. No real database or deployment was provisioned for you. No claim of security certification is made.

## Run yourself before accepting customers

### Database and server credentials

- [ ] setup.sql runs successfully on a new project.
- [ ] Both final public-privilege booleans in setup.sql are false.
- [ ] On an empty TEST project, verify.sql completes with its PASS notice and rolls back.
- [ ] Real Streamlit Secrets are stored only in the Streamlit settings, not in GitHub.
- [ ] Admin 1111 works initially and changing it is required.
- [ ] The old admin password fails after changing it; the new password works.
- [ ] Customer cannot open admin functions through the UI. Public/anon key cannot execute salon_api directly.
- [ ] Cron job is active and a completed run is visible. With a throwaway OLD test record, confirm the deletion policy works before keeping real personal data.

### Two customer devices and one admin device

- [ ] Open the public app in a normal phone browser and an incognito/second browser.
- [ ] Create two different customer codes; save both PINs privately.
- [ ] Hide/show the code and confirm no private information appears in the public calendar.
- [ ] Make a booking as customer A; check the correct name/comment is visible to Dad.
- [ ] Customer B sees only that the time is reserved, without A's name/comment/service/price.
- [ ] Try booking the same time from two devices almost simultaneously; only one active booking should succeed.
- [ ] Mark another time unavailable as Dad while a customer has it visible; check automatic refresh and rejection if the customer submits stale availability.
- [ ] Mark a time tentative; customer request becomes pending and holds the slot. Approve/reject from Dad's page and check customer history updates.
- [ ] Cancel as the customer and as Dad; verify the slot can be booked again when its underlying rule allows it.
- [ ] Recover customer A with A's code/PIN on another device. The previous token stops working, existing bookings transfer, and expiry is not extended.
- [ ] Wrong PIN cannot retrieve the customer's data. After the failed-login limit, wait for the 15-minute window rather than repeatedly guessing.

### Schedule and pricing

- [ ] Save recurring lunch and weekly day-off rules; check at least two weeks.
- [ ] Override a recurring rule on one date; confirm other dates do not change.
- [ ] Delete a rule after reading the whole-repeat deletion warning.
- [ ] Change a date's price; customer sees it after selecting that date.
- [ ] Add a service with the plus button, save, and book it.
- [ ] Confirm prior bookings retain their original prices when the menu changes.
- [ ] Change base prices and verify separately overridden dates keep their own menus.
- [ ] Make sure the offered services really fit the fixed 30-minute model.

### Mobile, QR, operations

- [ ] Check at approximately 360px-wide Android Chrome and iPhone Safari; no unusable tap targets or cut-off controls.
- [ ] Week grid scrolls sideways; all seven date buttons remain usable; day buttons open the intended date.
- [ ] Service selection, add/remove price items, repeated schedule settings, dialog dismissal, and reopening work on real touchscreens.
- [ ] Print a QR from the admin page and scan with another phone. Public app loads without your personal login.
- [ ] Record real shop name/address/phone and prices, replace samples, configure all recurring closures.
- [ ] Confirm code expiry behavior with an artificial TEST session expiry; do not change live tables casually. Expired code must not cancel the reservation.
- [ ] Establish a phone fallback, backup/restore plan, provider monitoring, and a review of the privacy notice before launch.

## Re-run offline checks

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python tools/check_sql_syntax.py
```

The GitHub workflow runs the same checks on Python 3.12 when GitHub Actions is enabled. Local tests for this package ran on Python 3.13. Do not interpret a green mocked test suite as proof that your live keys, SQL installation, or hosting are correctly configured.
