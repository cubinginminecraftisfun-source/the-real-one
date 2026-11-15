"""Korean, QR-accessible Streamlit salon reservations. Entry point: app.py."""
import html
from datetime import date, datetime, timedelta
from io import BytesIO

import qrcode
import streamlit as st
from db import Store, UserError
from logic import KST, STATUSES, now, blocks, status_at, overlaps, can_book

st.set_page_config(page_title='우리동네 헤어 · 예약', page_icon='✂️', layout='centered')
st.markdown('''<style>
.stApp {background:#f7f9fc;color:#17243b}
.block-container {max-width:850px;padding-top:1.5rem;padding-bottom:3rem}
h1,h2,h3 {letter-spacing:-.04em}
.stButton button,.stFormSubmitButton button {min-height:48px;border-radius:14px;font-weight:650}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px}
.hero {padding:28px 24px;border-radius:24px;background:#e8f0fe;margin-bottom:20px}
.hero h1 {margin:8px 0;color:#174ea6;font-size:2.1rem}
.hero p {margin:8px 0;color:#354c6c}
.badge {background:white;color:#1967d2;border-radius:20px;padding:6px 12px;font-size:13px}
.week-scroll {overflow-x:auto;border-radius:16px;border:1px solid #dbe3ef;margin:14px 0}
.week-grid {border-collapse:collapse;min-width:650px;width:100%;background:white;font-size:12px}
.week-grid th {padding:12px 4px;background:#edf3ff;position:sticky;top:0}
.week-grid td {padding:9px 3px;text-align:center;border:1px solid #edf0f5}
.slot-available {background:#e6f4ea;color:#146c2e}
.slot-maybe {background:#fff4ce;color:#754e00}
.slot-unavailable {background:#f1f3f4;color:#5b616a}
.slot-booked {background:#dce8ff;color:#174ea6;font-weight:bold}
@media(max-width:600px){.block-container{padding:1rem .8rem 3rem}.hero{padding:20px}h1{font-size:1.8rem!important}}
</style>''', unsafe_allow_html=True)


def setting(key, default):
    try:
        return st.secrets.get('shop', {}).get(key, default)
    except FileNotFoundError:
        return default


SHOP = setting('name', '우리동네 헤어')
ADDRESS = setting('address', '매장 주소를 설정해 주세요')
PHONE = setting('phone', '매장 전화번호를 설정해 주세요')
OPEN, CLOSE = int(setting('opening_hour', 10)), int(setting('closing_hour', 20))
if not (0<=OPEN<CLOSE<=23):
    st.error('영업시간 설정을 확인해 주세요. 시작 < 종료, 0~23시 범위입니다.')
    st.stop()
try:
    # DATABASE CONNECTION HERE: copied from Supabase Connect > Session pooler.
    # No API key is required. NEVER paste credentials directly into this file.
    DATABASE_URL = st.secrets['DATABASE_URL']
except (KeyError, FileNotFoundError):
    st.error('데이터베이스 연결 설정이 필요합니다. README의 Supabase 설정을 따라 주세요.')
    st.stop()


@st.cache_resource
def get_store(url, opening, closing):
    store = Store(url, opening, closing)
    store.initialize()
    return store


def stamp(day):
    return datetime.combine(day, datetime.min.time(), KST)


def logout():
    if st.session_state.get('role')=='admin':
        store.logout_admin(st.session_state['token'])
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def fail(exc):
    if isinstance(exc, UserError):
        st.warning(str(exc))
    else:
        # Do not leak connection strings, SQL statements or personal data in errors.
        st.error('연결 또는 저장에 실패했습니다. 잠시 후 새로고침해 주세요. 계속되면 관리자에게 문의해 주세요.')


def week_table(day, rules, booked):
    monday = day-timedelta(days=day.weekday())
    days = [monday+timedelta(days=i) for i in range(7)]
    headers = ''.join(f'<th>{d:%m/%d}<br>{"월화수목금토일"[d.weekday()]}</th>' for d in days)
    rows = []
    for t in blocks(day, OPEN, CLOSE):
        cells = []
        for d in days:
            moment = t.replace(year=d.year, month=d.month, day=d.day)
            occupied = any(overlaps(moment,moment+timedelta(minutes=30),b['starts_at'],b['ends_at']) for b in booked)
            status = 'booked' if occupied else status_at(rules,moment)
            label = '예약됨' if occupied else STATUSES[status]
            cells.append(f'<td class="slot-{status}">{label}</td>')
        rows.append(f'<tr><td>{t:%H:%M}</td>{"".join(cells)}</tr>')
    st.markdown(f'<div class="week-scroll"><table class="week-grid"><thead><tr><th>시간</th>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',unsafe_allow_html=True)
    st.caption('↔ 주간표는 좌우로 밀어서 확인하세요. 날짜 선택은 아래 달력에서 가능합니다.')


@st.dialog('날짜별 가격표', width='small')
def price_dialog(day, admin=False):
    st.caption(f'{day:%Y년 %m월 %d일} · 가격 단위: 원(₩)')
    items = store.prices(day)
    if not admin:
        if not items:
            st.info('이 날짜의 가격표가 아직 없습니다. 매장에 문의해 주세요.')
        for item in items:
            st.markdown(f"**{html.escape(item['label'])}** · ₩{item['price']:,} · {item['duration']}분")
        return
    st.caption('＋ 행 추가로 시술을 등록하세요. 적용은 선택한 날짜 하루입니다.')
    import pandas as pd
    frame = pd.DataFrame(items, columns=['label','price','duration']).astype({'price':'Int64','duration':'Int64'})
    edited = st.data_editor(frame, num_rows='dynamic', hide_index=True, width='stretch',
        column_config={
            'label':st.column_config.TextColumn('시술명', required=True, max_chars=50),
            'price':st.column_config.NumberColumn('가격 (₩)', min_value=0, max_value=10_000_000, step=1000, format='₩%d', required=True),
            'duration':st.column_config.SelectboxColumn('소요 시간 (분)', options=[30,60,90,120], required=True)})
    st.caption('표 아래 ＋ 또는 빈 행을 눌러 추가합니다. 미입력 행은 삭제해 주세요.')
    if st.button('가격표 저장', type='primary', use_container_width=True):
        try:
            if edited.isna().any().any():
                raise UserError('모든 행의 시술명, 가격, 시간을 입력해 주세요.')
            store.save_prices(st.session_state['token'],day,edited.to_dict('records'))
            st.session_state['flash']='가격표를 저장했습니다.'
            st.rerun()
        except Exception as e:
            fail(e)
    copy_day = st.date_input('다른 날짜의 가격표 가져오기', day, key='copy_price_day')
    if st.button('이 날짜로 복사하여 저장',use_container_width=True):
        try:
            store.save_prices(st.session_state['token'],day,store.prices(copy_day))
            st.session_state['flash']='가격표를 복사했습니다.'
            st.rerun()
        except Exception as e:
            fail(e)


@st.dialog('예약하기', width='small')
def booking_dialog(start):
    st.subheader(f'{start:%m월 %d일 %H:%M}')
    items = store.prices(start.date())
    if not items:
        st.info('이 날짜의 가격표가 준비되지 않았습니다. 매장에 문의해 주세요.')
        return
    rules, booked = store.calendar(stamp(start.date()), stamp(start.date()+timedelta(days=1)))
    items = [item for item in items if can_book(rules,booked,start,item['duration'],OPEN,CLOSE)]
    if not items:
        st.info('시술에 필요한 연속 시간이 부족합니다. 다른 시작 시간을 선택해 주세요.')
        return
    with st.form('booking_form'):
        label = st.selectbox('시술 선택', [i['label'] for i in items],
              format_func=lambda label: next(f"{i['label']} · ₩{i['price']:,} · {i['duration']}분" for i in items if i['label']==label))
        name = st.text_input('이름', max_chars=40)
        phone = st.text_input('연락처', placeholder='01012345678', max_chars=14)
        comment = st.text_area('요청 사항 (선택)',max_chars=500,placeholder='원하는 스타일 등을 남겨 주세요.')
        st.caption('예약 운영을 위해 이름·연락처·요청 사항을 매장 관리자가 확인합니다. 방문 종료 90일 후 삭제 대상이며 관리자가 정리합니다. 민감한 개인정보는 적지 마세요.')
        agree = st.checkbox('개인정보 수집·이용 안내를 확인하고 동의합니다.')
        submit = st.form_submit_button('예약 확정', type='primary', use_container_width=True)
    if submit:
        if not agree:
            st.warning('개인정보 안내를 확인해 주세요.')
            return
        try:
            store.book(st.session_state['token'],start,label,name,phone,comment)
            st.session_state['flash']='예약이 확정되었습니다. 내 예약에서 확인해 주세요.'
            st.rerun()
        except Exception as e:
            fail(e)


@st.fragment(run_every='10s')
def calendar_view(admin=False):
    st.subheader('예약 캘린더')
    st.caption('한국 시간 · 10초마다 자동 갱신 · 예약 최종 확정 시 중복 확인')
    mode = st.radio('보기', ['일간','주간'], horizontal=True, key='calendar_mode')
    day = st.date_input('날짜 선택', value=now().date(), min_value=now().date()-timedelta(days=365) if admin else now().date(),
                        max_value=now().date()+timedelta(days=60), key='calendar_day')
    if st.session_state.get('price_mode'):
        st.info('가격표 날짜를 선택한 뒤 아래 버튼을 눌러 주세요.')
        if st.button(('선택한 날짜 가격 편집' if admin else '선택한 날짜 가격 확인'), type='primary',use_container_width=True):
            price_dialog(day, admin)
    begin = day-timedelta(days=day.weekday()) if mode=='주간' else day
    rules, booked = store.calendar(stamp(begin),stamp(begin+timedelta(days=7 if mode=='주간' else 1)))
    if mode=='주간':
        week_table(day,rules,booked)
    st.caption('🟢 예약 가능 · 🟡 상담 필요 · ⚪ 예약 불가 · 🔵 예약됨')
    st.markdown(f'**{day:%m월 %d일} · {"월화수목금토일"[day.weekday()]}요일**')
    for start in blocks(day,OPEN,CLOSE):
        occupied = any(overlaps(start,start+timedelta(minutes=30),b['starts_at'],b['ends_at']) for b in booked)
        status = status_at(rules,start)
        label = '🔵 예약됨' if occupied else {'available':'🟢 예약 가능','maybe':'🟡 상담 필요','unavailable':'⚪ 예약 불가'}[status]
        disabled = admin or occupied or status!='available' or start<=now()
        if st.button(f'{start:%H:%M}  ·  {label}',key=f'slot_{start.isoformat()}',disabled=disabled,use_container_width=True):
            booking_dialog(start)
    if not admin:
        st.caption(f'상담 필요 시간은 온라인 예약이 불가합니다. 전화 문의: {PHONE}')


def my_bookings():
    st.subheader('내 예약')
    rows = store.bookings(st.session_state['token'])
    if not rows:
        st.info('아직 예약이 없습니다.')
    for b in rows:
        with st.container(border=True):
            st.markdown(f"**{b['starts_at']:%m/%d %H:%M} — {b['ends_at']:%H:%M}**")
            st.write(f"{b['service']} · ₩{b['price']:,} · {'취소됨' if b['state']=='cancelled' else '예약 확정'}")
            st.write(f"이름: {b['customer_name']} / 연락처: {b['phone']}")
            if b['comment']:
                st.text(b['comment'])
            if b['state']=='confirmed' and b['starts_at']>now():
                confirm = st.checkbox('이 예약을 취소하겠습니다.', key=f'confirm_{b["id"]}')
                if st.button('예약 취소',key=f'cancel_{b["id"]}',disabled=not confirm):
                    store.cancel(st.session_state['token'],b['id'])
                    st.rerun()


def schedule_editor():
    st.subheader('시간 변경 / 반복 일정')
    st.caption('기본은 영업시간 내 예약 가능입니다. 겹치는 규칙은 나중에 저장한 것이 우선합니다. 기존 예약은 자동 취소되지 않습니다.')
    with st.form('schedule'):
        start = st.date_input('시작 날짜', now().date())
        kind = st.selectbox('반복', ['하루만','매주 반복','매일 반복'])
        weekdays = st.multiselect('매주 반복 요일',list(range(7)),default=[0,1,2,3,4,5],format_func=lambda x:'월화수목금토일'[x])
        forever = st.checkbox('종료 없이 반복 (반복 일정에만 적용)',value=True)
        end = st.date_input('반복 종료 날짜 (종료 없이 반복 해제 시)',now().date()+timedelta(days=30))
        options = list(range(OPEN*60,CLOSE*60+1,30))
        first = st.selectbox('시작 시간',options[:-1],format_func=lambda x:f'{x//60:02}:{x%60:02}')
        last = st.selectbox('종료 시간',options[1:],index=len(options)-2,format_func=lambda x:f'{x//60:02}:{x%60:02}')
        status = st.selectbox('표시 상태', list(STATUSES),format_func=lambda x:STATUSES[x])
        submitted = st.form_submit_button('일정 적용',type='primary',use_container_width=True)
    if submitted:
        try:
            until = start if kind=='하루만' else (None if forever else end)
            wd = [start.weekday()] if kind=='하루만' else (list(range(7)) if kind=='매일 반복' else weekdays)
            store.add_rule(st.session_state['token'],start,until,wd,first,last,status)
            st.success('일정이 적용되었습니다. 고객 화면은 10초 이내 갱신됩니다.')
        except Exception as e:
            fail(e)
    for r in reversed(store.list_rules(st.session_state['token'])):
        with st.expander(f"#{r['id']} · {STATUSES[r['status']]} · {r['start_date']} ~ {r['end_date'] or '계속'}"):
            st.write('요일: '+', '.join('월화수목금토일'[i] for i in r['weekdays']))
            st.write(f"{r['start_minute']//60:02}:{r['start_minute']%60:02} ~ {r['end_minute']//60:02}:{r['end_minute']%60:02}")
            check = st.checkbox('규칙 삭제 확인',key=f'del_rule_check_{r["id"]}')
            if st.button('이 규칙 삭제',key=f'del_rule_{r["id"]}',disabled=not check):
                store.delete_rule(st.session_state['token'],r['id'])
                st.rerun()


@st.fragment(run_every='10s')
def admin_bookings():
    st.subheader('주간 예약 고객')
    day = st.date_input('조회할 주',now().date(), key='admin_booking_week')
    monday = day-timedelta(days=day.weekday())
    rows = store.bookings(st.session_state['token'],True,stamp(monday),stamp(monday+timedelta(days=7)))
    if not rows:
        st.info('이 주의 예약이 없습니다.')
    for b in rows:
        with st.expander(f"{b['starts_at']:%m/%d %H:%M} · {b['customer_name']} · {'취소' if b['state']=='cancelled' else '확정'}"):
            st.write(f"{b['service']} · ₩{b['price']:,} · 종료 {b['ends_at']:%H:%M}")
            st.text(f"연락처: {b['phone']}\n요청: {b['comment'] or '없음'}")
            if b['state']=='confirmed':
                confirm = st.checkbox('고객에게 안내했으며 취소합니다.',key=f'admin_confirm_{b["id"]}')
                if st.button('예약 취소',key=f'admin_cancel_{b["id"]}',disabled=not confirm):
                    store.cancel(st.session_state['token'],b['id'],True)
                    st.rerun()


def password_form():
    st.subheader('관리자 비밀번호 변경')
    with st.form('password'):
        old = st.text_input('현재 비밀번호',type='password')
        new = st.text_input('새 비밀번호 (10자 이상)',type='password')
        repeat = st.text_input('새 비밀번호 확인',type='password')
        submit = st.form_submit_button('비밀번호 변경',type='primary')
    if submit:
        try:
            if new!=repeat:
                raise UserError('새 비밀번호가 일치하지 않습니다.')
            store.change_password(st.session_state['token'],old,new)
            for key in list(st.session_state):
                del st.session_state[key]
            st.session_state['flash']='비밀번호를 변경했습니다. 새 비밀번호로 로그인해 주세요.'
            st.rerun()
        except Exception as e:
            fail(e)


def home():
    st.markdown(f'<div class="hero"><span class="badge">편안한 방문, 간편한 예약</span><h1>✂ {html.escape(SHOP)}</h1><p>📍 {html.escape(ADDRESS)}</p><p>{html.escape(PHONE)}</p></div>',unsafe_allow_html=True)
    st.write('원하는 날짜와 시간을 고르면, 기다림 없이 방문할 수 있어요.')
    if st.button('처음 방문 · 시작하기',type='primary',use_container_width=True):
        st.session_state['token']=store.create_session()
        st.session_state['role']='customer'
        st.rerun()
    with st.expander('코드로 내 예약 확인 / 관리자 입장'):
        mode = st.radio('입장 구분',['고객','관리자'],horizontal=True)
        with st.form('login'):
            code = st.text_input('2자리 이용 코드',max_chars=2) if mode=='고객' else ''
            secret = st.text_input('비공개 복구 키' if mode=='고객' else '관리자 비밀번호',type='password')
            submit = st.form_submit_button('입장하기',use_container_width=True)
        if mode=='고객':
            st.caption('코드와 복구 키는 발급 후 24시간 동안 유효합니다. 만료 후 예약은 매장에 문의하세요.')
        if submit:
            try:
                token = store.login(code,secret,mode=='관리자')
                st.session_state.update(token=token,role='admin' if mode=='관리자' else 'customer')
                st.rerun()
            except Exception as e:
                fail(e)
    st.caption('운영 시간: '+f'{OPEN:02}:00 ~ {CLOSE:02}:00 · 온라인 예약은 60일 이내')


def customer_page():
    session = store.customer(st.session_state['token'])
    col1,col2 = st.columns([3,1])
    col1.subheader('✂ '+SHOP)
    show = col2.toggle('코드 표시',value=False)
    if show:
        st.info(f"이용 코드: {session['code']} · 만료 {session['expires_at']:%m/%d %H:%M} (한국 시간)")
    else:
        col2.caption('코드 ••')
    with st.expander('내 코드 / 비공개 복구 키 확인 · 꼭 보관하세요'):
        st.write(f"이용 코드: **{session['code']}**")
        st.code(st.session_state['token'],language=None)
        st.caption(f"만료: {session['expires_at']:%Y-%m-%d %H:%M} 한국 시간. 다른 기기·새로고침 후 재입장에는 둘 다 필요합니다. 타인에게 공유하지 마세요.")
    st.warning('처음 이용하시면 위의 코드와 복구 키를 먼저 보관해 주세요. 24시간이 지나도 예약은 취소되지 않습니다.',icon='🔑')
    if st.button('가격 확인', use_container_width=True):
        st.session_state['price_mode']=True
        st.toast('캘린더에서 날짜를 선택해 주세요.')
    if st.session_state.get('price_mode') and st.button('가격 확인 모드 닫기'):
        st.session_state['price_mode']=False
    page = st.radio('메뉴',['예약하기','내 예약'],horizontal=True)
    if page=='예약하기':
        calendar_view()
    else:
        my_bookings()
    if st.button('처음으로 / 로그아웃',use_container_width=True):
        logout()


def admin_page():
    state = store.admin_state(st.session_state['token'])
    st.title('매장 관리')
    if state['must_change']:
        st.warning('초기 비밀번호 1111은 공개된 값입니다. 운영 전에 새 비밀번호로 변경해 주세요.')
        password_form()
        return
    page = st.radio('관리 메뉴',['캘린더','일정 변경','예약 고객','설정'],horizontal=True)
    if page=='캘린더':
        if st.button('가격 편집',use_container_width=True):
            st.session_state['price_mode']=True
            st.toast('캘린더에서 날짜를 선택해 주세요.')
        if st.session_state.get('price_mode') and st.button('가격 편집 모드 닫기'):
            st.session_state['price_mode']=False
        calendar_view(True)
    elif page=='일정 변경':
        schedule_editor()
    elif page=='예약 고객':
        admin_bookings()
    else:
        password_form()
        st.divider()
        st.subheader('매장 QR 코드')
        url = setting('public_url','')
        if url.startswith('https://'):
            img = qrcode.make(url)
            out = BytesIO()
            img.save(out,format='PNG')
            st.image(out.getvalue(),width=220)
            st.download_button('QR 이미지 다운로드',out.getvalue(),'salon_qr.png','image/png')
        else:
            st.info('배포 후 shop.public_url에 HTTPS 앱 주소를 설정하면 QR 코드가 표시됩니다.')
        st.subheader('개인정보 정리')
        st.caption('방문 종료 90일이 지난 예약·고객 정보를 영구 삭제합니다. 만료된 빈 세션도 정리합니다.')
        agree = st.checkbox('삭제 기준을 확인했습니다. 삭제 후 복구할 수 없습니다.')
        if st.button('90일 지난 예약 삭제',disabled=not agree):
            st.success(f"{store.purge(st.session_state['token'])}건 삭제했습니다.")
    if st.button('관리자 로그아웃',use_container_width=True):
        logout()


try:
    store = get_store(DATABASE_URL,OPEN,CLOSE)
    if 'flash' in st.session_state:
        st.success(st.session_state.pop('flash'))
    role = st.session_state.get('role')
    if role=='admin':
        admin_page()
    elif role=='customer':
        customer_page()
    else:
        home()
except Exception as e:
    fail(e)
    if isinstance(e,UserError) and st.button('처음 화면으로 돌아가기'):
        st.session_state.clear()
        st.rerun()
