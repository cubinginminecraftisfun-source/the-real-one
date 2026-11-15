# ✂ 우리동네 헤어 — Korean QR reservation app

A complete starter project for **one hairdresser / one chair at a time**, built with Streamlit + a Supabase PostgreSQL database. The interface is Korean. This guide is in English for the person setting it up; `아버지_사용설명서.md` is a short Korean guide for your father.

## First: what each service does

- **GitHub** holds the source files. GitHub Pages does NOT run Python/Streamlit apps.
- **Streamlit Community Cloud** runs `app.py` and gives you an HTTPS web address.
- **Supabase** stores bookings, prices, schedule rules, password hashes and 24-hour customer sessions. Restarting Streamlit does not erase them.
- A **QR code** opens that HTTPS web address on a phone. No app installation is required. It is a public entry QR, NOT a QR containing a customer's recovery key.

You need your own GitHub, Supabase and Streamlit accounts. No Google Calendar, Maps, SMS or other paid API is required by this implementation. Hosting/database providers may impose plan limits, charges or inactivity policies; check their current plans before relying on the app for business.

## What is implemented

| Requirement | Implementation |
|---|---|
| Korean start page | Shop name, address, phone, Start and combined customer/admin entrance |
| Random short code | A–Z/0–9, exactly 2 characters, unique among current allocations, valid 24 hours from issue |
| In-app code check | Hide/show control plus private recovery-key expander |
| Recover customer data | Two-character code **and** private recovery key; no account registration |
| Admin | Starts as `1111`, forces password change; stored salted PBKDF2 hash; change password in settings |
| Mobile calendar | Day view with large time buttons; horizontally scrollable week overview and date picker |
| Availability | Available / consultation needed / unavailable; existing reservations shown separately |
| Repeats | One day, weekly selected weekdays, daily; end date or no end |
| Live updates | Database polling every 10 seconds while the calendar/booking list is open |
| Prices | Price edit/check button → select date → open dialog; ＋/new row adds label, ₩ price and duration |
| Private bookings | Customers only get their own details; public calendar queries return times/status only |
| Admin bookings | Week selection; names, phones, comments, service, price and cancellation |
| QR | Generated and downloadable in admin settings after configuring the public URL |
| Double-booking | Serialized application writes plus PostgreSQL exclusion constraint on overlapping intervals |

### Deliberate differences and sensible defaults

1. **Two characters alone are NOT secure.** There are only 1,296 possibilities. A customer must also keep a random private recovery key. Only its SHA-256 hash is stored in the database. Never use short-code-only access for personal information.
2. **10-second refresh, not Supabase Realtime push.** Booking confirmation always rechecks the latest schedule and prices inside a locked database transaction. A stale-looking slot cannot successfully double-book.
3. This is a mobile-friendly Streamlit interpretation of Calendar-style day/week navigation, **not a pixel-perfect Google Calendar clone**. There is no drag-to-select, swipe gestures or direct editing of week-grid cells. Use the date picker and schedule form. Some native widget chrome/keyboard labels can follow the phone/browser locale.
4. Hours default to 10:00–20:00, in `Asia/Seoul`. All schedule boundaries use 30-minute blocks. Services can last 30/60/90/120 minutes. The full service interval must fit before closing and remain available.
5. `상담 필요` is visible but cannot be booked online. Customers are directed to telephone the shop. There is no pending-request/approval queue.
6. Prices are **per selected date**, not automatically recurring. Use the copy-from-date button to reuse a price list. Dates without prices show a notice and cannot accept bookings. No invented sample price list is published.
7. Reservations can be made up to 60 days ahead; up to 3 future active bookings per issued customer session. These are lightweight guardrails, not identity-based anti-spam protection.
8. Customer access expires 24 hours after issuance, even if the appointment is later. **The booking itself does not expire or cancel.** After 24 hours, customers must telephone the shop for details/cancellation. An admin can still see it. Consider a longer secure booking-management link for a later version.
9. There are no SMS, KakaoTalk, payment, email reminders, analytics trackers or location-map integrations. The address is text; QR scans open the app.

## Project files

```text
salon_app/
  app.py                         # Streamlit interface, forms, dialogs, QR
  db.py                          # PostgreSQL access + authorization + transactions
  logic.py                       # Scheduling and password/hash helpers
  schema.sql                     # Run once in Supabase SQL Editor
  requirements.txt               # Python dependencies
  .gitignore                     # Protects your real secrets from normal git add
  .streamlit/
    config.toml                  # Blue/white theme
    secrets.toml.example         # Template ONLY; no real credentials
  tests/
    test_logic.py                # Pure Python unit tests
  README.md
  아버지_사용설명서.md
  LAUNCH_CHECKLIST.md
```

# Step-by-step setup

## 1. Create your Supabase project

1. Open [Supabase](https://supabase.com/dashboard) and sign up/sign in.
2. Create a **new project** in your organization. Use a name such as `dad-hair-reservations`.
3. Choose a suitable region close to Korea if available.
4. Create a strong **database password** and store it in your password manager. This is NOT your Supabase website login password, NOT the salon admin password, and NOT an API key.
5. Wait for the database to finish provisioning.

Use a new project for this starter so you do not interfere with other applications' data or access policies.

## 2. Create the tables

1. In your Supabase project, open **SQL Editor**.
2. Click **New query**.
3. Open the supplied `schema.sql` file in a text editor, copy its entire contents, and paste them into SQL Editor.
4. Click **Run**.
5. Open **Table Editor** and confirm that tables beginning with `salon_` exist.

The SQL enables Row Level Security and revokes `anon`/`authenticated` access on these tables. **Do not disable RLS or add public read-all policies** to fix a connection problem. Customers never connect directly to the Data API.

The first successful app start creates the hashed initial admin password (`1111`) if no settings row exists. Later restarts do not reset it.

## 3. Get the database connection string

1. Click **Connect** at the top of your Supabase project.
2. Choose **Session pooler** / shared pooler session mode. This is commonly suitable for IPv4 hosting. Copy the **URI** connection string.
3. It will resemble this illustrative format (your actual hostname is provided by Supabase):

```text
postgresql://postgres.PROJECT_REF:[YOUR-PASSWORD]@POOLER_HOST:5432/postgres
```

4. Replace `[YOUR-PASSWORD]` with your database password. Keep the actual host and username copied from Supabase; do not try to guess them.
5. If the password contains reserved characters, percent-encode the password part only. Examples: `@` → `%40`, `#` → `%23`, `/` → `%2F`, `%` → `%25`, space → `%20`. Do not encode the whole URI. Do not paste a password into an online encoder. On your own computer you may use Python's `urllib.parse.quote(password, safe='')` if needed.

**No Supabase API key is required.** This app uses a server-only PostgreSQL connection. The exact credential location is `DATABASE_URL` in `.streamlit/secrets.toml.example`, marked **DATABASE PASSWORD HERE**. `app.py` reads that setting at the comment **DATABASE CONNECTION HERE**. There is no `API KEY HERE` placeholder because there is no API-key-based service to configure.

The default `postgres` connection is highly privileged. It must be kept server-side. This starter enforces customer/admin authorization in `db.py`, not Supabase Auth. A production security review and a least-privileged custom database role are recommended before a broad launch. Do not reuse this database credential in mobile/browser code.

## 4. Upload the project to GitHub

1. Extract the ZIP on your computer.
2. Create a new GitHub repository. A **private repository** is a sensible starting choice.
3. Upload the **contents** of the `salon_app` folder into the root of your repository. `app.py` should be at the repository's top level.
4. Ensure `.streamlit/config.toml`, `.streamlit/secrets.toml.example` and `.gitignore` are included. On some file browsers, names beginning with a dot are hidden; enable hidden-file display if needed.
5. Commit the files.

**Never upload `.streamlit/secrets.toml` with real values.** `.gitignore` helps when using Git, but it does not prevent you from manually uploading a secret through the GitHub website. Never put the real database connection string in `app.py`, README, screenshots, issues or commits. If exposed, rotate the database password immediately; deleting a GitHub file does not remove it from commit history.

You do not need to connect your GitHub account to this chat or give anyone your credentials.

## 5. Recommended: initialize and test locally before public deployment

Do this first so nobody else can claim the publicly known initial admin password.

Install Python 3.11 or 3.12 on your computer. Open a terminal **inside the extracted `salon_app` directory**:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

If your system calls Python `python3`, use `python3` to create the environment.

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Make a copy of `.streamlit/secrets.toml.example` named `.streamlit/secrets.toml`. Edit the copy, not the example. Put your actual connection URI in the root `DATABASE_URL` setting. Then change the shop name, address and phone:

```toml
DATABASE_URL = "YOUR_REAL_SUPABASE_SESSION_POOLER_URI"

[shop]
name = "아버지 미용실"
address = "실제 매장 주소"
phone = "실제 매장 전화번호"
opening_hour = 10
closing_hour = 20
public_url = ""
```

The `DATABASE_URL` line must remain **above** `[shop]`; otherwise TOML will put it inside the wrong section.

Run:

```bash
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Open the local address shown by Streamlit. On the start page:

1. Expand **코드로 내 예약 확인 / 관리자 입장**.
2. Select **관리자**.
3. Enter `1111` as the password.
4. The app requires a new password of at least 10 characters before it exposes admin controls.
5. Change it to a unique, strong password and store that password safely.
6. Log in again with the new password. Old admin sessions are invalidated.

If you cannot test locally, keep the hosted app access-restricted during initial setup, change `1111` immediately, and only then make it public and print a QR code. Do not publish the QR with the initial password unchanged.

## 6. Deploy on Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in using GitHub.
2. Choose **Create app** / deploy an app from GitHub.
3. Select your repository and branch (usually `main`).
4. Set the entry-point file to **`app.py`**.
5. Select Python 3.11 or 3.12 in deployment settings if offered.
6. Open **Advanced settings → Secrets**. Paste the complete contents of your real local `secrets.toml`. If you did not create it locally, fill in the supplied example directly in this secrets panel.
7. Click **Deploy**. Streamlit installs `requirements.txt` and runs the app.
8. If you initialized locally against the same Supabase project, your new admin password is already saved; use it instead of `1111`.

After deployment, secrets can be edited under **App settings → Secrets**. Never commit them to GitHub. Restart/reboot the app after changing configuration if necessary.

## 7. Add the shop URL and generate a QR

1. Copy the real public HTTPS URL of your deployed app.
2. In Streamlit's Secrets panel, change `shop.public_url` to that URL:

```toml
public_url = "https://YOUR-REAL-APP-ADDRESS.streamlit.app/"
```

Keep the original value of `DATABASE_URL` and all other settings. Save/restart if required.

3. Log in as admin → **설정 → 매장 QR 코드**.
4. Click **QR 이미지 다운로드**.
5. Print it with a short label, e.g. `미용실 예약 · QR을 스캔해 주세요`.
6. Test scanning it from both an iPhone and an Android phone before displaying it in the shop.
7. The app must be publicly accessible for walk-in customers. Test while signed OUT of GitHub/Streamlit and on mobile data, not only on your own logged-in computer.

Changing code in GitHub does not usually change the deployed app URL, so the QR can remain the same. If the actual URL changes, generate and print a new QR.

## 8. Set prices and your father's weekly schedule

### Prices (required before accepting reservations)

1. Admin → **캘린더 → 가격 편집**.
2. Select a date in **날짜 선택**.
3. Click **선택한 날짜 가격 편집** to open the dialog.
4. Use the table's ＋/new-row control to add services, for example a men's haircut. Enter your father's actual price (the app always displays ₩) and duration. Do not leave incomplete rows.
5. Click **가격표 저장**.
6. Repeat for dates you want to accept bookings on. The dialog can **copy prices from another date** so you do not have to retype each row.

Prices are snapshots at booking time. Editing a day's prices later does not silently change an already confirmed reservation's stored price or service duration. There is no payment collection; these are displayed reservation prices.

### Example: close every Sunday

1. Admin → **일정 변경**.
2. Start date: the first date the rule should apply.
3. Repeat: **매주 반복**.
4. Weekday: select only **일**.
5. Check **종료 없이 반복**.
6. Time range: your full business day.
7. Status: **예약 불가**.
8. Save.

### Example: lunch every day

Choose **매일 반복**, 12:00–13:00, **예약 불가**, no end date, then save.

### Example: might be available on one afternoon

Choose **하루만**, select that date and hours, set **상담 필요**, then save. Customers will see yellow consultation-needed blocks and cannot immediately book them online.

### Exceptions and editing

The newest matching schedule rule wins. To reopen one holiday afternoon, create a newer one-day **예약 가능** rule for those hours. To remove a rule, expand it in the schedule section, check the delete confirmation and delete it. Removing the newest rule may reveal an older matching rule underneath.

Availability rules do **not** cancel existing confirmed bookings. Existing reservations continue to occupy their time, even if a new closed-time rule overlaps. Contact the customer and explicitly cancel/reschedule if necessary.

## Customer flow

1. Scan the QR → tap **처음 방문 · 시작하기**.
2. A short code and private recovery key are created. Open **내 코드 / 비공개 복구 키 확인** and save both somewhere private. No personal data appears in the URL.
3. View day/week availability. Tap **가격 확인**, select a date and open the price dialog if desired.
4. Tap an available start time → choose a service → enter name, telephone and optional comment → agree to the privacy notice → confirm.
5. **내 예약** shows only that customer's bookings. Future reservations can be cancelled after checking a confirmation box.
6. To reopen after a browser refresh, on another device or after logging out, enter **both** the short code and private recovery key within the original 24-hour window.
7. A browser refresh may reset Streamlit session state. Keep both credentials before leaving. The app intentionally does not put the recovery key into query strings or persist it in a browser cookie.
8. After 24 hours, call the shop. Making a new code does not recover an expired session's bookings.

## Privacy, security and operating limits

- Treat the private recovery key like a password. Do not print it on the public QR or send it in a public chat.
- Admin login expires after 8 hours. Changing the password invalidates all admin sessions. Initial `1111` cannot access admin data without first changing it, but someone who knows it could claim an uninitialized app: initialize privately first.
- Five failed attempts in a 15-minute window block that admin/customer-code bucket for 15 minutes, persisted in Supabase. This is not per-IP rate limiting. A determined attacker can deliberately lock a code bucket. Session issuance itself has no CAPTCHA; abuse controls should be strengthened for broad public release.
- There are at most **1,296 active two-character references** in a 24-hour period. Expired references can be reused, but a new session has a new ID/key and cannot inherit an old customer's bookings.
- Requests to book, cancel or change schedules are serialized using one PostgreSQL transaction-level advisory lock. A database exclusion constraint also prevents overlapping active reservations, including service duration.
- Availability polls are sanitized: the browser never receives other customers' names, telephone numbers, comments or session IDs. Admin authorization is checked again server-side before every private read/write; hiding a UI button is not the security boundary.
- Passwords and recovery keys are not stored in plaintext in the database. A recovery key necessarily exists in the customer's current server-side Streamlit session so it can be displayed to them.
- This is a single-worker schedule, not multi-staff scheduling. No timezone choice is offered; it is always Korean time.
- **Retention is manual.** Admin → Settings has an explicitly confirmed action to permanently remove bookings whose end time is more than 90 days ago and expired unreferenced sessions. No scheduler is configured and code expiration alone does not delete bookings. Run cleanup regularly or add a reviewed scheduled job; don't promise automatic 90-day deletion to customers.
- The in-app consent notice is a basic starter, not legal certification. Before collecting real customer data, have the shop owner review the actual privacy notice, lawful processing, retention, vendor/overseas processing arrangements, access permissions and local obligations. An expiring code does not by itself establish compliance.
- Streamlit Community Cloud/inactivity, mobile browser reconnect behavior, provider quotas and outages can affect availability. Have a telephone-booking fallback and a backup policy. Application-level customer data export, restore and automated backups are not implemented here; use/review Supabase's backup capabilities for your plan.

## Tests and honest verification status

Run the supplied pure-Python tests:

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py db.py logic.py tests
```

They check time blocks, repeating weekdays, inclusive rule end dates, newest-rule priority, overlap boundaries, cancelled-slot reuse, long service intervals, closing-time validation, past/unaligned starts and password hashing. Source files were also syntax-compiled during preparation.

**Not verified here:** a live Supabase instance, execution of the SQL against your database, actual Streamlit rendering on phone browsers, concurrent requests against a real database and your deployed HTTPS/QR. No credentials were provided. Complete `LAUNCH_CHECKLIST.md` before collecting real customer information. This is a working-code starter, not a claim of audited production readiness.

## Troubleshooting

| Symptom | Check |
|---|---|
| Database connection notice/error | Is root-level `DATABASE_URL` in Streamlit Secrets? Is the password URL-encoded? Did you copy the actual Session pooler URI? Is Supabase running? |
| `salon_` tables missing / app cannot start | Run the complete `schema.sql` in the same Supabase project as the connection string. Keep RLS enabled. |
| Can't sign in with `1111` | The password may already have been changed from a local run using the same database. Use that new password. Do not reset tables to fix this. |
| Forgotten admin password | A trusted project owner must perform a reviewed database-side password reset; this starter intentionally has no public reset endpoint. Do not share the database password or weaken RLS. |
| Too many login attempts | Wait 15 minutes. Don't keep refreshing and guessing. |
| Empty date cannot accept bookings | Add a price list for that exact date and ensure service duration fits all available blocks. |
| Customer code no longer works | Both short code and recovery key must match; the original issue time must be within 24 hours. Reservation still exists for admin. |
| Closed time still shows a reservation | Intentional: changing availability never cancels a customer's booking automatically. |
| Another person's booking visible as '예약됨' | Intentional: only occupied time is public; no personal details should appear. Report it if actual personal data appears. |
| QR opens an access/sign-in screen | The deployed app may be private or `public_url` is not the public app address. Test logged out/on mobile data. |
| Can't see hidden configuration files on upload | Enable hidden files and include the `.streamlit` folder, but NEVER the real `secrets.toml`. |

## Recommended next improvements

1. A secure per-booking management link lasting until the appointment, instead of a 24-hour-only management window.
2. Phone OTP and CAPTCHA/issuance rate limits; they require a separate provider and careful abuse handling.
3. KakaoTalk or SMS confirmations/reminders; sending requires a real provider, consent and backend integration, not just an API-key placeholder.
4. Batch/repeating price lists with date exceptions, instead of copying each date.
5. Multiple hairdressers/chairs only when needed; that requires a resource-aware overlap constraint, not just a second button.
6. Supabase Auth/MFA for admin and a least-privileged database role after security review.
7. Deployment browser tests, database concurrency/security integration tests, automated retention and backups/restore checks.

## Official references used

- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Streamlit secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Supabase Postgres connection methods and password encoding](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)

Setup documentation was checked on November 13, 2026; dashboard labels can change.
