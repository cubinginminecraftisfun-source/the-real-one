# Upgrade your EXISTING working app to V2

You already have a working Supabase database and Streamlit deployment. **Keep both. Do not create a new project, delete tables, or rerun setup.sql.**

## Before changing anything

1. Choose a quiet period and tell your father not to change bookings during the upgrade.
2. Save a copy of your current GitHub revision (commit ID / download ZIP).
3. Back up/export your Supabase database using the project's available backup/export facilities. Confirm you can restore it. Provider backup access depends on your plan.
4. Keep your existing Streamlit Secrets unchanged. Never upload secrets.toml or API keys.
5. Do not open the app to customers until both the database and files are updated.

## 1. Update your EXISTING Supabase database first

1. Extract this ZIP and open `hae_salon/supabase/migrate_v2.sql` in a text editor.
2. In your EXISTING Supabase project open **SQL Editor → New query**.
3. Copy ALL of migrate_v2.sql, paste it and Run **once**.
4. Wait for success. This script is wrapped in BEGIN/COMMIT; if there is an error, run `ROLLBACK;`, save the error text, and stop. Do not delete conflicting records/tables to force it through.
5. Do NOT run `setup.sql` or `setup_v1_reference.sql`. Those are not upgrades.

The migration adds booking end-times (existing appointments become 30 minutes), an overlap exclusion constraint, recurring-price storage, and the updated server function. It preserves customer names/comments, reservations, prices, rules, code expiry and the existing administrator password. It does not reset your password to 1111. PINs are no longer used. Existing code recovery signs out the old session, as before.

The migration is intended to run once from V1. A second run may report an existing constraint/table; do not keep rerunning it. If you installed any intermediate unfinished V2 SQL previously, stop and ask for an upgrade tailored to that schema.

## 2. Replace the application files in the SAME GitHub repository

1. Open the same GitHub repo used by Streamlit.
2. Choose Add file → Upload files.
3. Upload the CONTENTS of this ZIP's `hae_salon` folder, preserving subfolders. Commit the update.
4. Especially check these files exist:

```
app.py
salon/mobile.py
salon/db.py
salon/calendar_component.py
salon/calendar_frontend/index.html
salon/calendar_frontend/style.css
salon/calendar_frontend/app.js
requirements.txt
.streamlit/config.toml
```

Upload the whole project to avoid missing dependencies, but never real credentials. `archive/` is reference material only. `package.json` is for optional development tests; Streamlit does not require you to run npm or compile JavaScript. The frontend is already ordinary HTML/CSS/JS.

## 3. Restart the SAME Streamlit deployment

1. Keep the main file path `app.py`.
2. Keep your Supabase URL/key, AUTH_PEPPER, shop name/address/phone unchanged in Secrets.
3. APP_URL is no longer used; it can remain in Secrets harmlessly or be removed. There is no QR UI now. Your already printed QR still works if the public app URL stays the same.
4. Allow Streamlit to redeploy the GitHub commit, then choose Reboot if necessary.
5. Reload the app in the browser. A phone's old open page should be closed/reloaded to get the new scripts.
6. Log back in. Existing valid 24-hour codes work WITHOUT a six-digit PIN. Your father's existing password is unchanged; if never changed, it remains 1111. Password change is voluntary through the key icon.

## 4. Test before reopening to customers

Use two different devices or private-browser sessions:

- New customer: start → 2-character code. Eye hides/shows it. No PIN.
- Recover with that code only; confirm old device loses access on its next server check.
- Dad logs in without a forced-password screen; key icon opens password dialog with red X.
- Timeline displays 00:00–24:00. Only its center scrolls; header stays in place.
- Vertical scrolling does not change the date; deliberate horizontal swipe does. Try iPhone Safari and Android Chrome if available. Center arrows also navigate.
- Tap blank timeline / plus → initial 30-minute outline. Resize each edge; the time snaps to five minutes. Minimize and expand the bottom editor. Test the soft keyboard too.
- Save a future 10:05–10:50 reservation; another customer cannot reserve an overlapping interval.
- Dad sees the name/comment; another customer only sees an occupied block.
- Show seven-day bookings with 예약. Dad sees customer names; other customers do not.
- Create weekly unavailable time. Save a different state on one Monday WITHOUT repeat. Verify the next Monday stays on the recurring rule.
- Repeat the same test for prices; a one-date override must not change next week's price.
- Test daily/weekly, a final date (inclusive), and no end date.
- Confirm phone dialog + copy, won prices, red popup close buttons, and three-second success/warning/error toasts.
- Test approving/rejecting a tentative request and customer cancellation.

## Security trade-off you requested

Two characters are a convenience code, not strong identity verification. Anyone guessing an active code can access/cancel that customer's bookings. Login rate limiting remains, but does not make short codes secure. Eye-hide is visual only. Changing the known default admin password is still strongly recommended even though the app does not force it.

## Rollback caution

Do not drop the new end-time column or restore only the old function after customers start making variable-length reservations. V1 assumes 30-minute bookings and can misrepresent longer appointments. Restore the database AND compatible app revision together from a pre-upgrade backup only after reconciling new reservations with your father. If a migration or live test fails, pause customer use and share the error with credentials removed.
