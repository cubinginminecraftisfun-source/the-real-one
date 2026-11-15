"""해담살롱 예약 — Streamlit + Supabase. Read README.md before deploying."""
from datetime import date, timedelta
from html import escape
from io import BytesIO
import secrets
import qrcode
import streamlit as st
from salon import db
from salon.core import (STATE_LABEL, hhmm, monday, now_kst, parse_dt,
                        schedule_state, slot_dt, slot_state, validate_menu)
from salon.ui import CSS, week_html

st.set_page_config(page_title='미용실 예약',page_icon='✂️',layout='centered',initial_sidebar_state='collapsed')
st.markdown(CSS,unsafe_allow_html=True)


def configured():
    try:
        return bool(st.secrets.get('SUPABASE_URL') and
                    (st.secrets.get('SUPABASE_SECRET_KEY') or st.secrets.get('SUPABASE_SERVICE_ROLE_KEY')) and
                    st.secrets.get('AUTH_PEPPER'))
    except Exception:
        return False


def setting(key,default):
    return st.secrets.get(key,default) if configured() else default


def dismiss_dialog():
    st.session_state.pop('active_dialog',None)


def open_dialog(name,*args):
    st.session_state.active_dialog={'name':name,'args':args}
    st.rerun()


def toast(message):
    dismiss_dialog()
    st.session_state.flash=message


def reset():
    # Prevent a different customer on a shared device inheriting form widget values.
    nonce=st.session_state.get('client_nonce')
    st.session_state.clear()
    if nonce:
        st.session_state.client_nonce=nonce


def use_session(result):
    nonce=st.session_state.get('client_nonce',secrets.token_hex(24))
    reset()
    st.session_state.client_nonce=nonce
    for k,v in result.items():
        st.session_state[k]=v
    st.session_state.selected_day=now_kst().date()
    st.session_state.week_start=monday(now_kst().date())
    st.session_state.show_code=bool(result.get('pin'))
    st.session_state.view='day'
    st.rerun()


def run(action,payload=None,authenticated=True):
    try:
        return db.call(action,payload,authenticated)
    except db.AppError as exc:
        st.error(str(exc))
        if st.session_state.get('auth_expired'):
            if st.button('시작 화면으로',key='expired_home'):
                reset(); st.rerun()
        return None


@st.dialog('내 코드로 접속 · 관리자 접속',on_dismiss=dismiss_dialog)
def login_dialog():
    st.caption('고객: 두 자리 코드 + 복구 PIN / 관리자: 비밀번호만 입력')
    with st.form('login_form'):
        code=st.text_input('접속 코드 또는 관리자 비밀번호',type='password',max_chars=64)
        pin=st.text_input('고객 복구 PIN (숫자 6자리)',type='password',max_chars=6,help='관리자는 비워 두세요.')
        submit=st.form_submit_button('접속하기',type='primary',use_container_width=True)
    if submit:
        result=run('login',{'code':code.strip(),'pin':pin.strip()},False)
        if result:
            use_session(result)


@st.dialog('관리자 비밀번호 변경',on_dismiss=dismiss_dialog)
def password_dialog(forced=False):
    if forced:
        st.warning('기본 비밀번호 1111은 최초 설정용입니다. 먼저 변경해 주세요.')
    with st.form('password_form'):
        old=st.text_input('현재 비밀번호',type='password',max_chars=64)
        new=st.text_input('새 비밀번호 (8~64자)',type='password',max_chars=64)
        confirm=st.text_input('새 비밀번호 확인',type='password',max_chars=64)
        submit=st.form_submit_button('비밀번호 저장',type='primary',use_container_width=True)
    if submit:
        if new!=confirm:
            st.error('새 비밀번호가 서로 다릅니다.')
        elif len(new)<8:
            st.error('새 비밀번호를 8자 이상 입력해 주세요.')
        elif run('change_password',{'old':old,'new':new}):
            st.session_state.must_change=False
            toast('관리자 비밀번호를 변경했습니다.'); st.rerun()


@st.dialog('예약하기',on_dismiss=dismiss_dialog)
def booking_dialog(day,minute):
    # Re-read menu on every dialog interaction. DB independently re-checks availability and price.
    prices=run('prices',{'day':day.isoformat()})
    if not prices:
        return
    st.subheader(f'{day.month}월 {day.day}일 · {hhmm(minute)}')
    st.caption('한 분 / 30분 예약입니다. 장시간 시술은 매장에 먼저 문의해 주세요.')
    current=st.session_state.get('service_label')
    if current not in [x['label'] for x in prices['menu']]:
        st.session_state.service_label=prices['menu'][0]['label']
    st.write('시술을 선택해 주세요')
    for i,item in enumerate(prices['menu']):
        if st.button(f"{item['label']}  ·  ₩{item['price']:,}",key=f'svc_{i}',type='primary' if st.session_state.service_label==item['label'] else 'secondary',use_container_width=True):
            st.session_state.service_label=item['label']; st.rerun()
    chosen=next(x for x in prices['menu'] if x['label']==st.session_state.service_label)
    with st.form('booking_form'):
        name=st.text_input('이름 또는 별명',max_chars=30)
        comment=st.text_area('요청사항 (선택)',max_chars=300,placeholder='예: 옆머리를 짧게 부탁드려요. 민감한 정보는 적지 마세요.')
        st.caption('예약 운영을 위해 이름·시술·시간·요청사항을 저장합니다. 다른 고객에게는 공개되지 않습니다. 예약일로부터 30일 후 삭제하도록 관리합니다. 접속 코드 만료가 예약 취소를 뜻하지는 않습니다.')
        consent=st.checkbox('예약 정보 수집·이용에 동의합니다 (필수)')
        submit=st.form_submit_button('이 시간에 예약하기',type='primary',use_container_width=True)
    if submit:
        if not name.strip() or not consent:
            st.error('이름과 필수 동의를 확인해 주세요.'); return
        result=run('book',{'starts_at':slot_dt(day,minute).isoformat(),'name':name.strip(),'comment':comment.strip(),'service_label':chosen['label'],'expected_price':chosen['price'],'consent':consent})
        if result:
            toast('예약이 확정되었습니다.' if result['state']=='confirmed' else '승인 대기 중입니다. 매장 확인 후 확정됩니다.'); st.rerun()


@st.dialog('날짜별 가격표',on_dismiss=dismiss_dialog)
def price_dialog(day,admin=False):
    prices=run('prices',{'day':day.isoformat()})
    if not prices:
        return
    st.subheader(f'{day.month}월 {day.day}일 가격')
    st.caption('해당 날짜 전용 가격표' if prices['custom'] else '기본 가격표')
    if not admin:
        for item in prices['menu']:
            with st.container(border=True):
                st.write(item['label']); st.subheader(f"₩{item['price']:,}")
        st.caption('기존 예약에는 예약 당시 금액이 유지됩니다.'); return
    editor_id=day.isoformat()
    if st.session_state.get('price_editor_day')!=editor_id:
        st.session_state.price_editor_day=editor_id
        st.session_state.price_rows=[{'uid':secrets.token_hex(5),**x} for x in prices['menu']]
    for row in list(st.session_state.price_rows):
        uid=row['uid']
        with st.container(border=True):
            row['label']=st.text_input('시술 이름',value=row['label'],max_chars=30,key='pl_'+uid)
            row['price']=st.number_input('가격 (₩ 원)',min_value=0,max_value=10000000,value=int(row['price']),step=1000,key='pp_'+uid)
            st.caption(f"₩{row['price']:,}")
            if len(st.session_state.price_rows)>1 and st.button('항목 삭제',key='pd_'+uid):
                st.session_state.price_rows=[r for r in st.session_state.price_rows if r['uid']!=uid]; st.rerun()
    if len(st.session_state.price_rows)<20 and st.button('＋ 시술 추가',use_container_width=True):
        st.session_state.price_rows.append({'uid':secrets.token_hex(5),'label':'','price':0}); st.rerun()
    default=st.checkbox('다른 날짜에도 적용되는 기본 가격표로 설정',help='이미 별도 가격을 지정한 날짜는 바뀌지 않습니다.')
    if st.button('가격 저장',type='primary',use_container_width=True):
        try:
            menu=validate_menu(st.session_state.price_rows)
        except ValueError as exc:
            st.error(str(exc)); return
        if run('save_prices',{'day':editor_id,'menu':menu,'default':default}):
            st.session_state.pop('price_editor_day',None); toast('가격표를 저장했습니다. 기존 예약 금액은 유지됩니다.'); st.rerun()
    if prices['custom'] and st.button('이 날짜를 기본 가격표로 되돌리기',use_container_width=True):
        if run('reset_prices',{'day':editor_id}):
            st.session_state.pop('price_editor_day',None); toast('기본 가격표를 사용합니다.'); st.rerun()


@st.dialog('시간 설정',on_dismiss=dismiss_dialog)
def rule_dialog(day,minute):
    st.subheader(f'{day.month}월 {day.day}일 · {hhmm(minute)}부터')
    st.caption('예약은 30분 단위입니다. 이미 받은 예약은 시간 설정을 바꿔도 취소되지 않습니다.')
    states=[('available','예약 가능'),('tentative','확인 필요'),('unavailable','예약 불가')]
    if 'rule_state' not in st.session_state:
        st.session_state.rule_state='unavailable'
    for key,label in states:
        if st.button(label,key='rs_'+key,type='primary' if st.session_state.rule_state==key else 'secondary',use_container_width=True):
            st.session_state.rule_state=key; st.rerun()
    close=int(st.session_state.get('close_min',1200))
    duration=st.number_input('설정 길이 (분)',min_value=30,max_value=close-minute,value=30,step=30)
    st.caption(f'{hhmm(minute)} → {hhmm(minute+duration)}')
    st.write('반복 방식')
    mode=st.session_state.get('repeat_mode','once')
    for key,label in [('once','이 날짜만'),('weekly','매주 반복'),('daily','매일 반복')]:
        if st.button(label,key='repeat_'+key,type='primary' if mode==key else 'secondary',use_container_width=True):
            st.session_state.repeat_mode=key; st.rerun()
    weekdays=[day.isoweekday()]
    end=day
    if mode!='once':
        if mode=='daily':
            weekdays=list(range(1,8))
        else:
            weekdays=[]
            st.caption('반복할 요일을 켜 주세요')
            for i,label in enumerate('월화수목금토일',1):
                if st.toggle(label+'요일',value=i==day.isoweekday(),key=f'wd_{day}_{i}'):
                    weekdays.append(i)
        forever=st.toggle('종료 없이 계속 반복',value=True)
        end=None if forever else st.date_input('반복 종료일',value=day+timedelta(days=90),min_value=day)
    if st.button('시간 설정 저장',type='primary',use_container_width=True):
        if not weekdays:
            st.error('반복할 요일을 하나 이상 선택해 주세요.'); return
        if run('save_rule',{'start_date':day.isoformat(),'end_date':end.isoformat() if end else None,'weekdays':weekdays,'start_min':minute,'end_min':minute+duration,'state':st.session_state.rule_state,'repeats':mode!='once'}):
            toast('시간 설정을 저장했습니다. 고객 화면에 약 10초 이내 반영됩니다.'); st.rerun()


@st.dialog('예약 취소',on_dismiss=dismiss_dialog)
def cancel_dialog(booking):
    dt=parse_dt(booking['starts_at'])
    st.write(f'{dt:%m월 %d일 %H:%M} 예약을 취소할까요?')
    st.caption('취소 후에는 해당 시간을 다른 고객이 예약할 수 있습니다.')
    if st.button('예약 취소 확정',type='primary',use_container_width=True):
        if run('cancel',{'id':booking['id']}):
            toast('예약을 취소했습니다.'); st.rerun()


def booking_cards(bookings,admin=False):
    if not bookings:
        st.info('예약 내역이 없습니다.'); return
    for b in bookings:
        dt=parse_dt(b['starts_at'])
        with st.container(border=True):
            st.subheader(f'{dt:%m/%d %H:%M} · {STATE_LABEL[b["state"]]}')
            st.text(f"{b['name']} · {b['service_label']} · ₩{b['price']:,}")
            if b['comment']:
                st.text('요청: '+b['comment'])
            if dt>now_kst() and b['state'] in ('confirmed','pending'):
                if admin and b['state']=='pending':
                    cols=st.columns(2)
                    if cols[0].button('예약 승인',key='ok_'+b['id'],type='primary',use_container_width=True):
                        if run('decide',{'id':b['id'],'state':'confirmed'}):
                            toast('예약을 승인했습니다.'); st.rerun()
                    if cols[1].button('요청 반려',key='no_'+b['id'],use_container_width=True):
                        if run('decide',{'id':b['id'],'state':'rejected'}):
                            toast('요청을 반려했습니다.'); st.rerun()
                if st.button('예약 취소',key='cancel_'+b['id'],use_container_width=True):
                    open_dialog('cancel',b)


@st.fragment(run_every='10s')
def live_area(admin):
    start=st.session_state.week_start
    cal=run('calendar',{'from':start.isoformat()})
    if not cal:
        return
    st.session_state.close_min=cal['close_min']
    day=st.session_state.selected_day
    st.caption('자동 새로고침 · '+parse_dt(cal['server_now']).strftime('%H:%M:%S')+' KST')
    st.markdown('<div class="legend"><span style="background:#DDF2E9">예약 가능</span><span style="background:#FFF0C2">확인 필요 / 대기</span><span style="background:#E8EBEF">예약 불가</span><span style="background:#DBEAFE">예약됨</span></div>',unsafe_allow_html=True)
    if st.session_state.view=='week':
        st.markdown(week_html(start,cal),unsafe_allow_html=True)
        st.caption('주간표는 좌우로 밀어 확인하세요. 위 날짜 버튼을 누르면 해당 날짜를 선택합니다.')
    st.subheader(f'{day.month}월 {day.day}일 {"월화수목금토일"[day.weekday()]}요일')
    if admin:
        st.caption('아래 시간 버튼을 눌러 가능 · 확인 필요 · 불가 또는 반복 일정을 설정하세요.')
    else:
        st.caption('확인 필요 시간은 신청 후 매장의 승인이 필요합니다.')
    minutes=list(range(cal['open_min'],cal['close_min'],30))
    with st.container(key='slot_grid'):
        for index in range(0,len(minutes),2):
            cols=st.columns(2)
            for col,minute in zip(cols,minutes[index:index+2]):
                state=slot_state(day,minute,cal)
                disabled=(not admin and state not in ('available','tentative')) or slot_dt(day,minute)<=now_kst() or day>now_kst().date()+timedelta(days=90)
                if col.button(f'{hhmm(minute)} · {STATE_LABEL[state]}',key=f'slot_{day}_{minute}',disabled=disabled,use_container_width=True):
                    if admin:
                        open_dialog('rule',day,minute)
                    else:
                        open_dialog('booking',day,minute)
    if admin:
        st.subheader('이번 주 예약 고객')
        bookings=run('admin_bookings',{'from':start.isoformat()})
        if bookings:
            booking_cards(bookings['bookings'],True)
        st.subheader('이번 주에 적용되는 시간 설정')
        st.caption('특정 날짜 설정이 반복 설정보다 우선하며, 같은 유형에서는 나중에 저장한 설정이 우선합니다.')
        for r in cal['rules']:
            with st.container(border=True):
                days=' · '.join('월화수목금토일'[i-1] for i in r['weekdays'])
                st.text(f"{STATE_LABEL[r['state']]} · {hhmm(r['start_min'])}–{hhmm(r['end_min'])}")
                st.caption(f"{r['start_date']} → {r['end_date'] or '계속'} / {days}")
                if st.button('시간 설정 삭제',key=f"delrule_{r['id']}",use_container_width=True):
                    open_dialog('delete_rule',r['id'])
    else:
        st.subheader('내 예약 내역')
        bookings=run('my_bookings')
        if bookings:
            booking_cards(bookings['bookings'])


@st.dialog('시간 설정 삭제',on_dismiss=dismiss_dialog)
def delete_rule_dialog(rule_id):
    st.warning('이 설정 전체를 삭제할까요? 반복 일정이면 반복 전체가 삭제됩니다. 예약 내역은 유지됩니다.')
    if st.button('삭제 확정',type='primary',use_container_width=True):
        if run('delete_rule',{'id':rule_id}):
            toast('시간 설정을 삭제했습니다.'); st.rerun()


def home():
    name=setting('SHOP_NAME','해담살롱')
    location=setting('SHOP_ADDRESS','매장 주소를 설정해 주세요')
    st.markdown(f'<div class="hero"><div class="eyebrow">나를 위한 예약</div><h1>{escape(name)}</h1><p>{escape(location)}<br>기다림은 줄이고, 여유는 더하세요.</p></div>',unsafe_allow_html=True)
    st.caption(setting('SHOP_PHONE','')+' · 10:00–20:00 · 30분 단위')
    if not configured():
        st.info('아직 매장 연결 전입니다. README의 Supabase 설정과 Streamlit Secrets 등록을 완료해 주세요.'); return
    if st.button('새 예약 시작하기',type='primary',use_container_width=True):
        result=run('create_session',authenticated=False)
        if result:
            use_session(result)
    if st.button('내 코드로 확인 · 관리자 접속',use_container_width=True):
        open_dialog('login')
    st.caption('접속 코드는 발급 시점부터 24시간 동안 유효합니다. 새 기기에서 접속하면 이전 기기는 로그아웃됩니다.')
    st.caption('코드가 만료되어도 예약은 유지됩니다. 이후 확인·변경은 매장으로 문의해 주세요.')


def main():
    if not st.session_state.get('token'):
        home(); return
    status=run('session')
    if not status:
        return
    admin=status['kind']=='admin'
    st.session_state.kind=status['kind']
    if msg:=st.session_state.pop('flash',None):
        st.success(msg)
    st.caption('매장 관리' if admin else '나를 위한 예약')
    st.title(setting('SHOP_NAME','해담살롱'))
    if st.button('로그아웃 · 시작 화면',use_container_width=True):
        if run('logout'):
            reset(); st.rerun()
    if admin and status['must_change']:
        st.warning('안전한 시작을 위해 기본 비밀번호 1111을 변경해 주세요.')
        if st.button('첫 비밀번호 설정',type='primary',use_container_width=True):
            open_dialog('password',True)
        return
    if admin:
        if st.button('관리자 비밀번호 변경',use_container_width=True):
            open_dialog('password')
    else:
        top=st.columns([2,1])
        top[0].caption('내 접속 코드 · '+('공개 중' if st.session_state.get('show_code') else '숨김'))
        if top[1].button('숨기기' if st.session_state.get('show_code') else '코드 보기',use_container_width=True):
            st.session_state.show_code=not st.session_state.get('show_code'); st.rerun()
        if st.session_state.get('show_code'):
            with st.container(border=True):
                st.subheader('내 코드  '+status['code'])
                if st.session_state.get('pin'):
                    st.text('복구 PIN  '+st.session_state.pin)
                else:
                    st.caption('복구 PIN은 처음 발급받은 번호를 사용해 주세요.')
                st.caption('만료: '+parse_dt(status['expires_at']).strftime('%m/%d %H:%M')+' · 이 화면을 안전하게 보관하세요.')
    today=now_kst().date()
    st.session_state.setdefault('selected_day',today)
    st.session_state.setdefault('week_start',monday(today))
    st.session_state.setdefault('view','day')
    start=st.session_state.week_start
    st.subheader(f'{start:%Y년 %m월} · {start.day}일–{(start+timedelta(days=6)).day}일')
    nav=st.columns(3)
    if nav[0].button('‹ 이전 주',disabled=start<=monday(today),use_container_width=True):
        st.session_state.week_start=start-timedelta(days=7); st.session_state.selected_day=st.session_state.week_start; st.rerun()
    if nav[1].button('오늘',use_container_width=True):
        st.session_state.week_start=monday(today); st.session_state.selected_day=today; st.rerun()
    if nav[2].button('다음 주 ›',disabled=start+timedelta(days=7)>today+timedelta(days=90),use_container_width=True):
        st.session_state.week_start=start+timedelta(days=7); st.session_state.selected_day=st.session_state.week_start; st.rerun()
    cols=st.columns(2)
    for col,key,label in zip(cols,('day','week'),('일간 보기','주간 보기')):
        if col.button(label,type='primary' if st.session_state.view==key else 'secondary',use_container_width=True):
            st.session_state.view=key; st.rerun()
    if st.button('가격 수정' if admin else '가격 확인',use_container_width=True):
        st.session_state.price_mode=True; st.rerun()
    if st.session_state.get('price_mode'):
        st.info('아래에서 가격을 확인하거나 수정할 날짜를 눌러 주세요.')
        if st.button('날짜 선택 취소',use_container_width=True):
            st.session_state.price_mode=False; st.rerun()
    with st.container(key='date_strip'):
        cols=st.columns(7)
        for i,col in enumerate(cols):
            day=start+timedelta(days=i)
            if col.button(f'{"월화수목금토일"[i]} {day.day}',key=f'date_{day}',type='primary' if day==st.session_state.selected_day else 'secondary',use_container_width=True):
                st.session_state.selected_day=day
                if st.session_state.get('price_mode'):
                    st.session_state.price_mode=False
                    st.session_state.active_dialog={'name':'prices','args':(day,admin)}
                st.rerun()
    live_area(admin)
    if admin:
        st.divider()
        st.subheader('고객에게 공유하기')
        app_url=setting('APP_URL','')
        if app_url.startswith('https://'):
            qr=qrcode.make(app_url)
            buf=BytesIO(); qr.save(buf,format='PNG')
            st.image(buf.getvalue(),width=200)
            st.download_button('매장 QR 코드 저장',data=buf.getvalue(),file_name='salon-qr.png',mime='image/png',use_container_width=True)
            st.caption(app_url)
        else:
            st.info('배포 후 Secrets의 APP_URL을 입력하면 공유 QR 코드가 나타납니다.')
        st.caption('QR에는 앱 공개 주소만 들어갑니다. 관리자 비밀번호·고객 코드·API 키는 포함되지 않습니다.')


def dispatch_dialog():
    active=st.session_state.get('active_dialog')
    if not active:
        return
    functions={'login':login_dialog,'password':password_dialog,'booking':booking_dialog,
               'prices':price_dialog,'rule':rule_dialog,'cancel':cancel_dialog,
               'delete_rule':delete_rule_dialog}
    handler=functions.get(active['name'])
    if handler:
        handler(*active['args'])


main()
dispatch_dialog()
