# 해담살롱 · Korean QR reservation app

A mobile-first, single-hairdresser reservation app built with **Streamlit + Supabase**, ready to put in your own GitHub repository. The shop name/address are examples: replace them before sharing.

**Start here:** follow sections 1–7 in order. You do not need to edit Python to set the shop name, address, phone number, or credentials.

## What is included

- Korean customer and administrator screens, large tap targets, day/week views.
- No radio-button lists, selectboxes, multiselect dropdowns, or expandable section headers in the application code. Basic checkboxes are used for consent and one price option; switches are used for repeat days.
- Start screen → new two-character code, or existing-code/admin login.
- Customer code valid for exactly 24 hours from creation; show/hide inside the app.
- A six-digit recovery PIN accompanies the short code. Keep both private.
- Available / might be available / unavailable schedule states.
- Unmarked times inside opening hours are available.
- One-date, weekly (choose weekdays), or daily schedule rules; optional end date or indefinite repetition.
- Customer booking, own-history lookup, cancellation; pending bookings for uncertain times.
- Admin week-wide booking list with customer name, service, amount, and comment; approve or reject pending requests.
- Price button → date-selection notice → tap a date → price pop-up. Admin can add/remove services with the plus button and set won prices. Optional base-price changes.
- Public QR-code generation after you enter the deployment URL.
- PostgreSQL transaction lock and unique active-slot index protect against duplicate bookings.
- Private database schema, server-side permission checks, password hashing, authentication throttling, and no other customers' personal details in calendar responses.

### Important choices and limits — please read

1. **One hairdresser / one chair, fixed 30-minute appointments, 10:00–20:00 Korea time.** Last start is 19:30. Booking horizon is 90 days. This version is suitable for cuts, not multi-hour treatments. Blocking 30 minutes for a perm would not be safe: do not offer long treatments until service durations are implemented.
2. **Live means polling about every 10 seconds while the page is open and connected**, not push/WebSocket Supabase Realtime. Sleeping browser tabs and slow connections may take longer. The database always checks availability again when a customer submits.
3. **Two characters alone are not safe authentication.** There are only 1,296 A–Z/0–9 combinations. Returning customers use the short code **plus** a six-digit PIN. The actual browser session uses a high-entropy token kept server-side. This security adjustment is deliberate.
4. **Recovering a code transfers the login to the new session and signs out the old device.** It does not extend the original 24-hour expiry. Refreshing/reopening may require recovery; browser storage is not used to persist secrets. Initial PIN display is one-time, although it remains visible in that original session when unhidden. Save it safely.
5. **Expiry does NOT cancel an appointment.** After 24 hours the customer must phone the shop for lookup/cancellation. A newly issued code is a separate customer session and does not recover older reservations. The administrator retains access to the bookings.
6. **Admin login starts at `1111`, then requires a new 8–64 character password.** Admin sessions expire after eight hours. Do not publish the QR before changing the default password.
7. A tentative-time request holds the slot while awaiting approval. There is no automatic pending timeout. Dad should approve/reject promptly. An unavailable rule does not automatically cancel an existing confirmed/pending booking; cancel that booking explicitly if needed.
8. This is a tap-based calendar, **not Google's drag-and-drop UI**, and it does not connect to Google Calendar. The week overview scrolls horizontally on small phones; choose the day using the seven date buttons, then tap its large time buttons below. No pixel-identical Google replica is claimed.
9. No SMS, Kakao alerts, payment, customer accounts, or push notifications are included. Customers check approval inside the app within their code's lifetime or phone the shop afterward.
10. 1,296 active customer codes maximum; expired codes can be reused without exposing the previous customer's history. Each session can hold up to three future active bookings. New codes are limited to five per 15-minute client window; eight failed logins lock that client window. IP-based limits may affect customers sharing the shop Wi-Fi. When an IP is unavailable, a session nonce is used, which provides weaker abuse protection.
11. This is a small-shop starter app, **not a security-audited production booking platform**. All API calls share a transaction lock for straightforward correctness, which limits scale. Have an experienced developer review it before high-volume/public promotion.

## Project files

```text
app.py                           Streamlit entry point
requirements.txt                 Runtime dependencies
requirements-dev.txt             Test-only dependencies
.streamlit/config.toml           Colors and Streamlit settings
.streamlit/secrets.toml.example   SAFE example, no real keys
.gitignore                       Excludes real local secrets
salon/core.py                    Calendar and menu logic
salon/db.py                      Server-side Supabase requests (API KEY HERE markers)
salon/ui.py                      Styling and read-only week grid
supabase/setup.sql               ONE-TIME schema + permission-checked RPC
supabase/retention.sql           Daily data-deletion job, after Cron is enabled
supabase/verify.sql              Optional rollback-only TEST-project smoke checks
tests/                          Automated offline tests; Supabase calls are mocked
tools/check_sql_syntax.py        Offline SQL/function syntax validation
.github/workflows/tests.yml     GitHub automated test workflow
아버지_사용안내.md                 Short Korean operating guide
TESTING.md                       What was tested / what still needs a live test
```

Hidden folders starting with a dot are part of the project. Do not omit `.streamlit` when uploading.

## 1. Create the accounts

You need accounts at:

- GitHub: <https://github.com>
- Supabase: <https://supabase.com>
- Streamlit Community Cloud: <https://share.streamlit.io>

GitHub stores the code. **GitHub Pages does not run Python/Streamlit.** Streamlit Cloud runs the app, and Supabase stores reservations. The QR simply opens the Streamlit app's public HTTPS address.

Check each provider's current limits and pricing before relying on a free plan. This project does not assume any specific free-plan quota, uptime promise, or automatic backup entitlement.

## 2. Create Supabase and initialize the database

1. In Supabase, create a **new project**. Use a new project rather than an existing database containing valuable tables.
2. Choose your organization, enter a project name such as `dad-salon`, and create a strong database password. Keep that password private. The app does NOT require the database password.
3. Choose an appropriate available region, preferably near Korea, and wait until the project is ready.
4. Open **SQL Editor → New query**.
5. Open this ZIP's `supabase/setup.sql` in a text editor. Copy **all** its contents into the SQL Editor and press **Run**.
6. Its last query should return `false` for both `anon_can_execute` and `authenticated_can_execute`. That is intentional: browsers and ordinary logged-in Supabase users must not call the booking RPC directly.
7. This script creates a schema named `salon_private` and a public function named `salon_api`. In the Table Editor, you may need to change the schema filter to see the private tables. Do **not** expose `salon_private` through the Data API and do not add permissive RLS policies.
8. Leave `public` available as an exposed Data API schema: the server calls `public.salon_api` through it.

**Run setup.sql only once.** It intentionally does not silently overwrite existing tables or reset an existing administrator password. If you see `relation already exists`, stop instead of deleting live data. For a failed first-time experiment, creating a separate clean test project is safest.

### Optional database check before deployment

On a **new empty test project**, immediately after setup, run `supabase/verify.sql`. It tests initial admin login, password change, code creation/recovery, an appointment, rejection of a duplicate appointment, ownership checks, and calendar privacy. It rolls back its changes, so the initial password remains `1111`. It refuses to run if it sees existing bookings and assumes the example base menu has not been changed. It is not a concurrency/load test.

**I have not executed this script against your Supabase account. You must run it yourself.** If your SQL editor leaves a transaction open after an error, execute `ROLLBACK;` first.

### Enable the personal-data deletion job

1. In Supabase, enable **Cron / pg_cron** using the project's Integrations or Database area. Menu names can change; search the dashboard for Cron.
2. Run all of `supabase/retention.sql` **once** in SQL Editor.
3. Verify the `salon-daily-retention` job is active in the Cron dashboard and inspect its first run for errors.
4. The job runs daily at 03:10 Korea time. Booking records, including comments/names, are deleted once the appointment time is more than 30 days old; actual deletion is at the next daily run, not exactly on the 30-day second. Expired sessions and older configuration records are also cleaned.

Do this before taking real customer data because the app's consent notice describes that retention policy. This is a practical software default, **not legal advice or a complete privacy notice**. Add your shop's operator/contact information and obtain appropriate advice about privacy notices, hosting locations, and handling requests. Never invite customers to enter medical or other sensitive information in comments. Review provider backup-retention policies too; deleting live rows is not a promise to purge every provider backup instantly.

## 3. Find the Supabase URL and server-only key

1. In the Supabase project dashboard, find the **Project URL** in Connect or Project Settings / API. It looks like `https://abcdefgh.supabase.co`.
2. Open **Project Settings → API Keys** (dashboard wording may vary).
3. Copy/create a **Secret key** starting with `sb_secret_`. This has server-level privileges. Do **not** use the publishable or anon key for this app.
4. A legacy `service_role` JWT (usually starting `eyJ`) is supported as an alternative if your project exposes legacy keys. The example configuration explains the alternative variable name.

These credentials belong **only in Streamlit Secrets**, never in GitHub, browser JavaScript, an image, a QR code, a customer message, or a screenshot. The Python backend holds the key and checks every customer's token through the database function. If a key ever becomes public, rotate it in Supabase immediately; deleting the visible text from a Git commit does not remove it from history.

API locations:

- `.streamlit/secrets.toml.example`: every required value is labeled **API KEY HERE**.
- `salon/db.py`, `call()`: reads the Supabase URL/key and makes the server-side request.
- `salon/db.py`, `client_id()`: reads `AUTH_PEPPER`, your own random secret for hashing client identifiers.
- No paid calendar, map, QR, or messaging API is required. QR images are generated locally by the app.

## 4. Upload the app to GitHub

1. Unzip the download. Enter the `hae_salon` folder: this is the project root.
2. On GitHub, create a repository such as `dad-salon-booking`. A private repository is a sensible starting choice; choose visibility according to your Streamlit deployment/account options.
3. Upload the **contents** of `hae_salon`, including all subfolders. `app.py` and `requirements.txt` should be at the repository root, not inside another unnecessary wrapper folder.
4. Make sure `.streamlit/config.toml` and `.streamlit/secrets.toml.example` are present. Some file pickers hide dot-folders. If necessary use GitHub's Create new file with the exact path or upload through Git locally.
5. Commit the files.
6. **Do not create or upload `.streamlit/secrets.toml` on GitHub.** Only the `.example` file is safe. `.gitignore` protects normal Git workflows but is not a guarantee against manually uploading a secret in the website.
7. The included GitHub Actions workflow runs offline tests on pushes and pull requests. No database keys are needed for those tests.

Optional local Git upload, if you already use Git:

```bash
cd hae_salon
git init
git add .
git commit -m "Add Korean salon booking app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/dad-salon-booking.git
git push -u origin main
```

Replace the repository URL. Never paste an access token into a file or this command's URL.

## 5. Deploy on Streamlit Community Cloud

1. Sign into Streamlit Community Cloud and connect the GitHub account/repository.
2. Choose **Create app / Deploy an app**, then select your repository and branch (`main`).
3. Set the **main file path** to `app.py`.
4. In advanced settings, choose **Python 3.12** if offered. The repository's automated workflow also targets 3.12. The local verification for this delivery used Python 3.13.
5. Find **Secrets** in the deployment form, or open the app's settings → Secrets after creating it.
6. Paste the following, replacing every placeholder. Keep the quotation marks:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_SECRET_KEY = "API KEY HERE - your sb_secret_ server-only key"
AUTH_PEPPER = "API KEY HERE - your own long random value"
SHOP_NAME = "아버지 미용실"
SHOP_ADDRESS = "실제 매장 도로명 주소와 층수"
SHOP_PHONE = "실제 매장 전화번호"
APP_URL = ""
```

Generate a random `AUTH_PEPPER` on your own computer if Python is installed:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Use the resulting 64 characters, not the command itself. If you do not have Python, a reputable password manager can generate a random value of similar strength; do not reuse the admin password. Do not ask a stranger to generate your real deployment secrets.

Legacy key alternative: omit `SUPABASE_SECRET_KEY` and set `SUPABASE_SERVICE_ROLE_KEY = "your legacy service_role JWT"` instead. **Choose one.** If both are present, the new `SUPABASE_SECRET_KEY` wins.

7. Save secrets and deploy/reboot. Runtime dependencies come from `requirements.txt`; `requirements-dev.txt` is only for developers.
8. Open the app URL and check the Korean shop name and address.
9. If public sharing is offered, make the app accessible to customers without Streamlit organization sign-in. Test it in a private/incognito browser window. Anyone who can reach the public app can create a customer code, by design.

The placeholders in `requirements.txt` are **not** where API keys go; never put keys in dependency files.

## 6. First admin login and QR

1. Open the deployed app.
2. Tap **내 코드로 확인 · 관리자 접속**.
3. Enter **1111** in the first field. Leave the customer PIN field empty.
4. Tap **접속하기**, then **첫 비밀번호 설정**.
5. Enter current password `1111`; choose a unique new 8–64 character password, and confirm it. Store it in a password manager.
6. Set regular days off and lunch breaks before accepting bookings. Initially all times between 10:00 and 20:00 are open every day.
7. Review prices: the example defaults are **남성 커트 ₩15,000** and **여성 커트 ₩20,000**. They are sample prices, not your father's actual prices.
8. Copy the deployed HTTPS app URL. Return to Streamlit Secrets, set `APP_URL` to that exact URL, save, and reboot if prompted.
9. In the admin page, scroll to **고객에게 공유하기**. Tap **매장 QR 코드 저장** to download the PNG.
10. Scan the QR with another phone using its normal camera. Confirm it opens the public customer start screen. Print it only after testing.

If you change your app's URL later, regenerate and replace printed QR codes. The QR is a static app link, not an individual customer's code or an admin link.

## 7. Using the app

### Father/admin: schedule

- Choose **주간 보기** to inspect seven days at once, swiping the grid horizontally on a phone if needed.
- Tap a day in the seven-button date strip. Tap one of that day's time buttons below.
- Choose **예약 가능**, **확인 필요**, or **예약 불가**.
- Enter the block length in minutes, in 30-minute steps. A whole-day closure starting at 10:00 has length **600 minutes**, ending 20:00.
- Choose **이 날짜만**, **매주 반복**, or **매일 반복**. Weekly rules let you turn weekdays on/off. For a permanent repeating schedule, leave **종료 없이 계속 반복** on.
- Save. Open customer calendars normally reflect the new setting on the next approximately ten-second refresh.
- Under the week, the booking list shows private details to the admin only. Use **예약 승인** or **요청 반려** for a pending booking. Cancellation asks for confirmation.
- Saved time rules are listed too. To change a block, save a replacement rule for the desired times; to remove an entire rule, use its delete action and confirm. Deleting a repeating rule deletes that entire repeating definition, not just one occurrence.

**Priority:** a one-date rule always overrides a repeating rule. Between rules of the same type, the most recently saved wins. A one-off vacation closure can therefore override normal weekly opening. Setting time available is an explicit override, not merely deleting a closure. Existing reservations remain reserved regardless of rule edits.

### Father/admin: prices

1. Tap **가격 수정**. A message asks you to choose a date.
2. Tap the target day in the date strip.
3. In the pop-up, edit service names and **가격 (₩ 원)**, or tap **＋ 시술 추가**.
4. Each date supports 1–20 uniquely named services, each up to ₩10,000,000. These limits prevent accidental extreme input, not recommended shop prices.
5. Tap **가격 저장**. By default only that date changes.
6. To change the fallback menu used on other dates, tick **다른 날짜에도 적용되는 기본 가격표로 설정**. Dates with their own separate menus retain those overrides.
7. Use **이 날짜를 기본 가격표로 되돌리기** to remove a date override. Previously booked appointments keep their original quoted price.

### Customer

1. Scan QR → **새 예약 시작하기**.
2. Save the displayed two-character code **and** six-digit PIN privately. Use **숨기기 / 코드 보기** to hide/show them.
3. Choose a date. Tap an available time. **확인 필요** means you may request it but the shop must approve it.
4. Tap a service, enter name/nickname and an optional comment, read/accept the booking-data notice, and submit.
5. Read the result: **예약 확정** is confirmed; **승인 대기** is not yet confirmed. A pending request already holds the time against other bookings.
6. View **내 예약 내역**. Only your own data appears there. Other customers see the occupied slot, not your name/comment/service/price.
7. Within 24 hours, return via **내 코드로 확인 · 관리자 접속** using code + PIN. This replaces your old device session.
8. Use **예약 취소** to cancel a future active reservation, then confirm. To reschedule, cancel and book another slot; this is not an atomic rescheduling flow, so your new desired slot might be taken in between.
9. To view the menu without booking, tap **가격 확인**, then choose a date.

## 8. Run locally (optional)

Use Python 3.12 or 3.13 on your own computer:

```bash
cd hae_salon
python -m venv .venv
```

Activate it:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Then:

```bash
python -m pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, fill real values locally, and run:

```bash
python -m streamlit run app.py
```

Use the local address Streamlit prints. A QR pointing to `localhost` does not work on a customer's phone; public QR use requires the deployed HTTPS URL. If you cannot activate a virtual environment, use its Python executable directly rather than installing globally.

Developer checks:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python tools/check_sql_syntax.py
```

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| App says 아직 매장 연결 전 | Missing URL, secret key, or AUTH_PEPPER in Streamlit Secrets. Save and reboot. |
| HTTP 401 / 403 | Wrong project/key; anon or publishable key instead of a server secret; missing service_role execute grant. Never fix this by granting anonymous access. |
| HTTP 404 / function not found | setup.sql not run in that project; wrong project URL; public Data API schema unavailable. Check the SQL Editor/function list and retry from the UI after fixing setup. |
| HTTP 400 / 500 | Check private Streamlit logs and Supabase logs. Ensure setup.sql completed and input/config is valid. Do not publish logs containing secrets or customer data. |
| Tables seem missing | Switch Table Editor's schema to salon_private; data intentionally is not in public tables. |
| Old customer device stops working | Expected after recovery on another device, or after original 24-hour expiry. |
| Code expired but slot remains booked | Expected. Code expiry never cancels a booking. Phone the shop. |
| Login temporarily blocked | Eight failed logins in the current 15-minute window; shared Wi-Fi can share limits. Wait for the window to end. |
| A calendar edit did not open a booked time | Bookings take precedence; Dad must explicitly cancel/reject the reservation if appropriate. |
| A weekly edit does not override a date | One-date exceptions have higher priority. Remove/update the exception. |
| Customer does not see an edit immediately | Wait around ten seconds in an active tab; check internet or reopen. Submission always revalidates in the database. |
| No QR displayed | APP_URL must be the real HTTPS deployment URL. |
| Duplicate/time changed error on submit | Someone else booked it or Dad changed availability; choose another time. |
| Connection failed after submitting | The request may have committed before the connection dropped. Check 내 예약 내역 BEFORE booking again. Writes are not automatically retried. |
| Forgotten admin password | There is no customer-facing reset. The project owner can use the private recovery procedure below. |

### Owner-only admin recovery

Use Supabase SQL Editor only if you own the project. Do not run this as part of ordinary setup; it is an emergency reset. It does not delete bookings. Replace the quoted password with a new private 8–64 character value (not an actual example from this file), then execute:

```sql
begin;
select pg_advisory_xact_lock(820150001);
update salon_private.settings
set password_hash = extensions.crypt(
    encode(extensions.digest('REPLACE_WITH_YOUR_NEW_PRIVATE_PASSWORD','sha256'),'hex'),
    extensions.gen_salt('bf',10)),
    must_change = true
where id;
delete from salon_private.sessions where kind = 'admin';
commit;
```

Log in using your replacement password; the app will require changing it again. SQL Editor history can retain your query, so restrict project access and use a temporary unique recovery value. Never post it in a GitHub issue.

## 10. Customization / suggested next improvements

- Put the real salon name/address/phone in Secrets first; these are not hardcoded as your father's real details.
- Use indefinite weekly rules for lunch and regular holidays; use one-date rules for vacations.
- If changing opening hours/horizon, edit `v_open`, `v_close`, `v_horizon` inside `public.salon_api` and update matching UI labels/90-day navigation defaults in `app.py`. Update ONLY the function via a reviewed migration; **do not rerun the entire initial setup.sql on a live project**. Ask a developer for this change.
- Recommended next: per-service duration (30/60/90/120 minutes), reliable SMS/Kakao confirmation, secure longer-lived customer recovery, accessible full booking-date navigation, and a way for Dad to add phone/walk-in reservations. Until walk-ins are implemented, mark those times **예약 불가** manually.
- Booking-data export, restore drills, monitored alerts, stronger edge-level abuse protection/CAPTCHA, and a privacy review are recommended before depending on the app for daily trade.

## Official references

- Streamlit deployment: <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app>
- Streamlit secrets: <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management>
- Streamlit dialogs: <https://docs.streamlit.io/1.50.0/develop/api-reference/execution-flow/st.dialog>
- Supabase API keys (server-only versus public): <https://supabase.com/docs/guides/api/api-keys>
- Supabase Cron: <https://supabase.com/docs/guides/cron>

**Delivery status:** source files and offline tests are included. No GitHub repository, Streamlit deployment, Supabase account, database tables, or public URL was created on your behalf. You must perform the setup above, then the live checklist in TESTING.md, before sharing the QR with customers.
