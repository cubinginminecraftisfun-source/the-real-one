"""Server-only repository. Never send DATABASE_URL or raw booking rows to browsers.
Every write shares a transaction advisory lock; booking exclusion adds DB protection.
"""
import secrets
import string
import uuid
from contextlib import contextmanager
from datetime import timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from logic import now, password_hash, password_ok, digest, can_book, KST


class UserError(Exception):
    pass


class Store:
    def __init__(self, url, opening=10, closing=20):
        self.url, self.opening, self.closing = url, opening, closing

    @contextmanager
    def tx(self, write=False):
        # prepare_threshold=None supports Supabase transaction pooler.
        with psycopg.connect(self.url, sslmode='require', row_factory=dict_row,
                             prepare_threshold=None, connect_timeout=10) as conn:
            with conn.cursor() as c:
                c.execute("set time zone 'Asia/Seoul'")
                if write:
                    c.execute('select pg_advisory_xact_lock(84729101)')
                yield c

    def initialize(self):
        # This is called only once per application process, never resets passwords.
        with self.tx(True) as c:
            c.execute('select id from salon_settings where id=1')
            if not c.fetchone():
                c.execute('insert into salon_settings(id,password_hash) values(1,%s)',
                          (password_hash('1111'),))

    def _admin(self, c, token, allow_initial=False):
        c.execute('''select s.* from salon_settings s join salon_admin_sessions a
                     on a.auth_version=s.auth_version where s.id=1
                     and a.token_hash=%s and a.expires_at>now()''', (digest(token or ''),))
        row = c.fetchone()
        if not row:
            raise UserError('관리자 로그인이 만료되었습니다. 다시 로그인해 주세요.')
        if row['must_change'] and not allow_initial:
            raise UserError('초기 비밀번호를 먼저 변경해 주세요.')
        return row

    def admin_state(self, token):
        with self.tx() as c:
            return self._admin(c, token, True)

    def _customer(self, c, token):
        c.execute('select * from salon_sessions where secret_hash=%s and expires_at>now()',
                  (digest(token or ''),))
        row = c.fetchone()
        if not row:
            raise UserError('이용 코드가 만료되었습니다. 새 코드를 만들거나 매장에 문의해 주세요.')
        return row

    def customer(self, token):
        with self.tx() as c:
            return self._customer(c, token)

    def create_session(self):
        token = secrets.token_urlsafe(18)
        sid, expiry = str(uuid.uuid4()), now()+timedelta(hours=24)
        with self.tx(True) as c:
            c.execute('delete from salon_codes where expires_at<=now()')
            c.execute('select code from salon_codes')
            used = {r['code'] for r in c.fetchall()}
            choices = [a+b for a in string.ascii_uppercase+string.digits
                       for b in string.ascii_uppercase+string.digits if a+b not in used]
            if not choices:
                raise UserError('오늘 발급 가능한 코드가 모두 사용 중입니다. 매장에 문의해 주세요.')
            code = secrets.choice(choices)
            c.execute('insert into salon_sessions(id,code,secret_hash,expires_at) values(%s,%s,%s,%s)',
                      (sid, code, digest(token), expiry))
            c.execute('insert into salon_codes values(%s,%s,%s)', (code, sid, expiry))
        return token

    def login(self, code, secret='', admin=False):
        # A shared persistent throttle prevents bypass by opening new browser sessions.
        # Admin has its own bucket; customer buckets use the short reference.
        code = code.strip().upper()
        bucket = 'admin' if admin else 'customer:'+code[:2]
        result = None
        with self.tx(True) as c:
            c.execute('insert into salon_login_limits(bucket) values(%s) on conflict do nothing', (bucket,))
            c.execute('select * from salon_login_limits where bucket=%s', (bucket,))
            limit = c.fetchone()
            if limit['blocked_until'] and limit['blocked_until'] > now():
                raise UserError('로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.')
            if limit['window_start'] < now()-timedelta(minutes=15):
                c.execute('update salon_login_limits set failures=0,window_start=now(),blocked_until=null where bucket=%s', (bucket,))
            if admin:
                c.execute('select * from salon_settings where id=1')
                s = c.fetchone()
                if password_ok(secret, s['password_hash']):
                    result = secrets.token_urlsafe(32)
                    c.execute('insert into salon_admin_sessions values(%s,%s,%s)',
                              (digest(result), s['auth_version'], now()+timedelta(hours=8)))
            else:
                c.execute('''select s.id from salon_codes a join salon_sessions s on s.id=a.session_id
                             where a.code=%s and a.expires_at>now() and s.expires_at>now()
                             and s.secret_hash=%s''', (code, digest(secret.strip())))
                if c.fetchone():
                    result = secret.strip()
            if result:
                c.execute('delete from salon_login_limits where bucket=%s', (bucket,))
            else:
                c.execute('''update salon_login_limits set failures=failures+1,
                blocked_until=case when failures+1>=5 then now()+interval '15 minutes' else null end
                where bucket=%s''', (bucket,))
        # Raise outside transaction so failed-attempt counters actually commit.
        if not result:
            raise UserError('입력 정보가 올바르지 않거나 유효 시간이 만료되었습니다.')
        return result

    def change_password(self, token, current, new):
        if len(new) < 10 or new == '1111':
            raise UserError('새 비밀번호는 10자 이상으로 설정해 주세요.')
        with self.tx(True) as c:
            s = self._admin(c, token, True)
            if not password_ok(current, s['password_hash']):
                raise UserError('현재 비밀번호가 올바르지 않습니다.')
            c.execute('update salon_settings set password_hash=%s,must_change=false,auth_version=auth_version+1 where id=1',
                      (password_hash(new),))
            c.execute('delete from salon_admin_sessions')

    def logout_admin(self, token):
        with self.tx(True) as c:
            c.execute('delete from salon_admin_sessions where token_hash=%s', (digest(token),))

    def _rules(self, c):
        c.execute('select * from salon_rules order by id')
        return c.fetchall()

    def calendar(self, start, end):
        with self.tx() as c:
            rules = self._rules(c)
            # Projection deliberately never selects personal data.
            c.execute('''select starts_at,ends_at,state from salon_bookings
                         where starts_at<%s and ends_at>%s and state='confirmed' ''', (end, start))
            return rules, c.fetchall()

    def prices(self, day):
        with self.tx() as c:
            return self._prices(c, day)

    def _prices(self, c, day):
        c.execute('select items from salon_prices where day=%s', (day,))
        row = c.fetchone()
        return row['items'] if row else []

    def save_prices(self, token, day, items):
        clean = []
        for item in items:
            label = str(item.get('label','')).strip()
            if not label:
                continue
            price, duration = int(item['price']), int(item['duration'])
            if len(label)>50 or not 0<=price<=10_000_000 or duration not in (30,60,90,120):
                raise UserError('시술명·가격·소요 시간을 확인해 주세요.')
            clean.append({'label':label,'price':price,'duration':duration})
        if not clean or len(clean)>30 or len({i['label'] for i in clean}) != len(clean):
            raise UserError('서로 다른 시술명을 1~30개 입력해 주세요.')
        with self.tx(True) as c:
            self._admin(c, token)
            c.execute('insert into salon_prices values(%s,%s) on conflict(day) do update set items=excluded.items',
                      (day, Jsonb(clean)))

    def add_rule(self, token, start, end, weekdays, first, last, status):
        if not weekdays or last<=first or (end and end<start) or status not in ('available','maybe','unavailable'):
            raise UserError('기간, 요일, 시작·종료 시간을 확인해 주세요.')
        with self.tx(True) as c:
            self._admin(c, token)
            c.execute('''insert into salon_rules(start_date,end_date,weekdays,start_minute,end_minute,status)
                         values(%s,%s,%s,%s,%s,%s)''', (start,end,weekdays,first,last,status))

    def list_rules(self, token):
        with self.tx() as c:
            self._admin(c, token)
            return self._rules(c)

    def delete_rule(self, token, rid):
        with self.tx(True) as c:
            self._admin(c, token)
            c.execute('delete from salon_rules where id=%s', (rid,))

    def book(self, token, start, service, name, phone, comment):
        name, phone, comment = name.strip(), phone.strip(), comment.strip()
        digits = ''.join(x for x in phone if x.isdigit())
        if not 1<=len(name)<=40 or not 9<=len(digits)<=11 or len(comment)>500:
            raise UserError('이름, 전화번호(9~11자리), 요청 사항(500자 이내)을 확인해 주세요.')
        start = start.astimezone(KST)
        if start.date()>now().date()+timedelta(days=60):
            raise UserError('예약은 오늘부터 60일 이내만 가능합니다.')
        with self.tx(True) as c:
            session = self._customer(c, token)
            items = self._prices(c, start.date())
            item = next((i for i in items if i['label']==service), None)
            if not item:
                raise UserError('가격표가 변경되었거나 등록되지 않았습니다. 다시 확인해 주세요.')
            c.execute("select count(*) as n from salon_bookings where session_id=%s and state='confirmed' and ends_at>now()", (session['id'],))
            if c.fetchone()['n']>=3:
                raise UserError('코드 하나당 진행 중인 예약은 최대 3건입니다.')
            end = start+timedelta(minutes=item['duration'])
            c.execute("select starts_at,ends_at,state from salon_bookings where starts_at<%s and ends_at>%s and state='confirmed'", (end,start))
            if not can_book(self._rules(c), c.fetchall(), start, item['duration'], self.opening,self.closing):
                raise UserError('선택한 시간이 변경되었거나 이미 예약되었습니다. 다른 시간을 선택해 주세요.')
            c.execute('''insert into salon_bookings(id,session_id,starts_at,ends_at,customer_name,phone,comment,service,price)
                         values(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                      (str(uuid.uuid4()),session['id'],start,end,name,digits,comment,item['label'],item['price']))

    def bookings(self, token, admin=False, start=None, end=None):
        with self.tx() as c:
            if admin:
                self._admin(c, token)
                c.execute('select * from salon_bookings where starts_at>=%s and starts_at<%s order by starts_at', (start,end))
            else:
                session = self._customer(c, token)
                c.execute('select * from salon_bookings where session_id=%s order by starts_at desc', (session['id'],))
            return c.fetchall()

    def cancel(self, token, bid, admin=False):
        with self.tx(True) as c:
            if admin:
                self._admin(c, token)
                c.execute("update salon_bookings set state='cancelled' where id=%s", (bid,))
            else:
                s = self._customer(c, token)
                c.execute("update salon_bookings set state='cancelled' where id=%s and session_id=%s and starts_at>now()", (bid,s['id']))

    def purge(self, token):
        # Explicit admin retention action, not coupled to 24h code expiry.
        with self.tx(True) as c:
            self._admin(c, token)
            c.execute("delete from salon_bookings where ends_at<now()-interval '90 days'")
            count = c.rowcount
            c.execute('''delete from salon_codes where expires_at<=now()''')
            c.execute('''delete from salon_sessions s where expires_at<=now()
                         and not exists(select 1 from salon_bookings b where b.session_id=s.id)
                         and not exists(select 1 from salon_codes a where a.session_id=s.id)''')
            c.execute('delete from salon_admin_sessions where expires_at<=now()')
            c.execute("delete from salon_login_limits where window_start<now()-interval '1 day'")
            return count
