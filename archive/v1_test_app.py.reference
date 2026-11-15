"""Streamlit UI smoke/interaction tests with a mocked database; NOT live Supabase tests."""
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import ast
from streamlit.testing.v1 import AppTest
from salon.core import monday, now_kst, slot_dt

APP=Path(__file__).resolve().parents[1]/'app.py'


def button(at,label):
    return next(b for b in at.button if b.label==label)


def make_app(admin=False,forced=False):
    at=AppTest.from_file(str(APP),default_timeout=15)
    at.secrets.update({'SUPABASE_URL':'https://demo.supabase.co',
                      'SUPABASE_SERVICE_ROLE_KEY':'eyJ.fake.server.key','AUTH_PEPPER':'b'*64,
                      'SHOP_NAME':'테스트 살롱','SHOP_ADDRESS':'테스트로 1','APP_URL':''})
    day=now_kst().date()+timedelta(days=1)
    for key,value in {'token':'test-token','kind':'admin' if admin else 'customer',
        'selected_day':day,'week_start':monday(day),'view':'day','show_code':False}.items():
        at.session_state[key]=value
    calls=[]
    def rpc(action,payload=None,authenticated=True):
        payload=payload or {}; calls.append((action,payload))
        if action=='session':
            return {'kind':'admin' if admin else 'customer','code':'A1','expires_at':(now_kst()+timedelta(hours=24)).isoformat(),'must_change':forced}
        if action=='calendar':
            return {'rules':[],'bookings':[],'open_min':600,'close_min':1200,'server_now':now_kst().isoformat()}
        if action in ('my_bookings','admin_bookings'):
            return {'bookings':[]}
        if action=='prices':
            return {'menu':[{'label':'남성 커트','price':15000},{'label':'여성 커트','price':20000}],'custom':False}
        if action=='create_session':
            return {'token':'new-token','kind':'customer','code':'B2','pin':'654321','expires_at':(now_kst()+timedelta(hours=24)).isoformat()}
        if action=='login':
            return {'token':'recovered-token','kind':'customer','code':'A1','expires_at':(now_kst()+timedelta(hours=23)).isoformat()}
        if action=='book':
            return {'ok':True,'state':'confirmed'}
        return {'ok':True}
    return at,rpc,calls


def assert_clean(at):
    assert not at.exception, '\n'.join(str(e.value) for e in at.exception)


def test_unconfigured_home():
    at=AppTest.from_file(str(APP),default_timeout=15).run()
    assert_clean(at)
    assert any('아직 매장 연결 전' in x.value for x in at.info)


def test_customer_day_and_week():
    at,rpc,_=make_app()
    with patch('salon.db.call',side_effect=rpc):
        at.run(); assert_clean(at)
        assert sum('예약 가능' in b.label and ':' in b.label for b in at.button)==20
        button(at,'주간 보기').click().run(); assert_clean(at)
        assert any('week-grid' in m.value for m in at.markdown)
        assert not any('관리자 비밀번호 변경'==b.label for b in at.button)


def test_code_visibility():
    at,rpc,_=make_app()
    with patch('salon.db.call',side_effect=rpc):
        at.run()
        button(at,'코드 보기').click().run(); assert_clean(at)
        assert any('내 코드  A1' in x.value for x in at.subheader)
        button(at,'숨기기').click().run(); assert_clean(at)
        assert not any('내 코드  A1' in x.value for x in at.subheader)


def test_forced_admin_password_hides_calendar():
    at,rpc,calls=make_app(admin=True,forced=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); assert_clean(at)
        assert any(b.label=='첫 비밀번호 설정' for b in at.button)
        assert not any(action=='calendar' for action,_ in calls)
        button(at,'첫 비밀번호 설정').click().run(); assert_clean(at)
        assert any(t.label=='현재 비밀번호' for t in at.text_input)


def test_admin_schedule_dialog():
    at,rpc,_=make_app(admin=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); assert_clean(at)
        button(at,'10:00 · 예약 가능').click().run(); assert_clean(at)
        assert any(b.label=='시간 설정 저장' for b in at.button)
        assert any(b.label=='매주 반복' for b in at.button)


def test_customer_booking_dialog_and_submit():
    at,rpc,calls=make_app()
    with patch('salon.db.call',side_effect=rpc):
        at.run()
        button(at,'10:00 · 예약 가능').click().run(); assert_clean(at)
        next(x for x in at.text_input if x.label=='이름 또는 별명').input('테스트 고객')
        next(x for x in at.checkbox if '수집·이용' in x.label).check()
        button(at,'이 시간에 예약하기').click().run(); assert_clean(at)
        book=next(p for a,p in calls if a=='book')
        assert book['name']=='테스트 고객'
        assert book['expected_price']==15000
        assert book['consent'] is True


def test_price_date_flow():
    at,rpc,_=make_app()
    with patch('salon.db.call',side_effect=rpc):
        at.run()
        button(at,'가격 확인').click().run(); assert_clean(at)
        assert any('날짜를 눌러' in x.value for x in at.info)
        first_date=next(b for b in at.button if b.key and b.key.startswith('date_'))
        first_date.click().run(); assert_clean(at)
        assert any('₩15,000' in x.value for x in at.subheader)


def test_admin_price_add():
    at,rpc,_=make_app(admin=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); button(at,'가격 수정').click().run()
        next(b for b in at.button if b.key and b.key.startswith('date_')).click().run()
        assert_clean(at)
        assert len([x for x in at.text_input if x.label=='시술 이름'])==2
        button(at,'＋ 시술 추가').click().run(); assert_clean(at)
        assert len([x for x in at.text_input if x.label=='시술 이름'])==3


def test_no_radio_dropdown_or_expanders():
    tree=ast.parse(APP.read_text(encoding='utf-8'))
    forbidden={'radio','selectbox','multiselect','expander','select_slider'}
    bad=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in forbidden]
    assert bad==[]
