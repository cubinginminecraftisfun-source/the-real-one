"""Pure scheduling/security helpers; all timestamps are timezone-aware."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
STATUSES = {'available': '예약 가능', 'maybe': '상담 필요', 'unavailable': '예약 불가'}


def now():
    return datetime.now(KST)


def password_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'{salt}${value}'


def password_ok(password, stored):
    salt, expected = stored.split('$')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return hmac.compare_digest(actual, expected)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def blocks(day, opening=10, closing=20):
    start = datetime.combine(day, datetime.min.time(), KST).replace(hour=opening)
    return [start + timedelta(minutes=30*i) for i in range((closing-opening)*2)]


def overlaps(a, b, c, d):
    return a < d and c < b


def rule_matches(rule, moment):
    day = moment.date()
    return (rule['start_date'] <= day and
            (rule['end_date'] is None or day <= rule['end_date']) and
            moment.weekday() in rule['weekdays'] and
            rule['start_minute'] <= moment.hour*60 + moment.minute < rule['end_minute'])


def status_at(rules, moment):
    # Most recently created matching rule overrides older rules.
    matches = [r for r in rules if rule_matches(r, moment)]
    return max(matches, key=lambda r: r['id'])['status'] if matches else 'available'


def can_book(rules, bookings, start, duration, opening=10, closing=20, clock=None):
    clock = clock or now()
    if duration not in (30, 60, 90, 120) or start <= clock:
        return False
    if start.second or start.microsecond or start.minute not in (0, 30):
        return False
    end = start + timedelta(minutes=duration)
    if start.date() != end.date() or start.hour < opening:
        return False
    if end.hour*60 + end.minute > closing*60:
        return False
    for i in range(duration//30):
        if status_at(rules, start + timedelta(minutes=i*30)) != 'available':
            return False
    return not any(overlaps(start, end, b['starts_at'], b['ends_at'])
                   for b in bookings if b.get('state', 'confirmed') == 'confirmed')
