# Before sharing the QR with real customers

## Configuration
- [ ] Run schema.sql in a new Supabase project; confirm all salon_ tables exist.
- [ ] Store the actual Session pooler URI in Streamlit Secrets as root-level DATABASE_URL.
- [ ] Do not upload real secrets.toml to GitHub.
- [ ] Configure shop name, address, phone, hours, and the real public HTTPS URL.
- [ ] Initialize privately and replace 1111 with a unique strong password before publishing.
- [ ] Confirm anonymous/authenticated Data API roles cannot read salon tables; leave RLS enabled.

## Functional tests on your deployment
- [ ] Create date-specific prices for booking days; verify ₩ display and service durations.
- [ ] Set a one-day closure, weekly closure, lunch break, consultation period and newer availability exception.
- [ ] Keep a separate customer browser open; check changes appear within 10 seconds.
- [ ] Book a service and confirm its entire duration is unavailable to other customers.
- [ ] Attempt the same time from two browsers: only one booking should succeed.
- [ ] Check long services cannot cross lunch, closure, another booking or closing time.
- [ ] Verify public customer view shows occupied times but no other customer's name, phone or comment.
- [ ] Recover your own booking using both short code and recovery key after refresh/on another device.
- [ ] Verify wrong keys fail; check persistent failed-login throttling.
- [ ] Verify cancelled slots become available again.
- [ ] Check admin weekly list includes details and customer comments.
- [ ] Confirm price edits do not change existing booking snapshots.
- [ ] Check expired customer credentials are rejected while the reservation remains for admin (requires waiting or a separate test database).
- [ ] Change admin password; verify prior admin sessions are invalidated.

## Mobile and operations
- [ ] Scan the downloaded public QR on iPhone and Android, signed out and on mobile data.
- [ ] Check day buttons, horizontally scrollable week grid, date picker, price dialog and add-row control.
- [ ] Review the shop's privacy notice, retention, vendor arrangements and access permissions before collecting real data.
- [ ] Decide who regularly runs the manual 90-day cleanup and checks database backups.
- [ ] Maintain a telephone fallback for outages or expired customer access.
- [ ] Review public issuance abuse protection and database least privilege before broad promotion.

## Verification already completed on the supplied source
11 pure-Python scheduling/security helper tests passed and Python syntax compilation passed.
A live database, SQL migration, deployed Streamlit UI, device behavior and concurrent database requests have NOT been verified here. Complete the checks above with your project credentials before launch.
