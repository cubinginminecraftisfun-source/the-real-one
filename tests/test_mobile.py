"""V2 intent adapter/privacy regressions. No live credentials required."""
from datetime import timedelta
from unittest.mock import Mock
import pytest
from salon.mobile import handle_event, get_view_data, MUTATIONS
from salon.core import now_kst
from salon import db


def event(action='refresh',payload=None,id='one'):
    return {'id':id,'action':action,'payload':payload or {}}


def test_code_only_login_preserves_expiry_not_pin():
    state={'auth_expired':True}
    call=Mock(return_value={'token':'SECRET','kind':'customer','code':'A1','expires_at':'tomorrow'})
    handle_event(event('login',{'code':'A1'}),state,call)
    call.assert_called_once_with('login',{'code':'A1'},authenticated=False)
    assert state['token']=='SECRET' and 'pin' not in state and 'auth_expired' not in state
    assert state['ack']['ok']


@pytest.mark.parametrize('kind',['admin','customer'])
def test_login_no_forced_password_gate(kind):
    s={};call=Mock(return_value={'token':'T','kind':kind,'must_change':True})
    handle_event(event('login',{'code':'1111'}),s,call)
    assert s['kind']==kind and s['ack']['ok']
    assert 'must_change' not in s


def test_replay_does_not_repeat_write_after_another_event():
    s={'token':'T'};call=Mock(return_value={'ok':True})
    handle_event(event('book'),s,call)
    handle_event(event('refresh',id='two'),s,call)
    handle_event(event('book'),s,call)
    assert call.call_count==1


def test_uncertain_network_error_not_retried():
    s={'token':'T'};call=Mock(side_effect=db.AppError('연결 불안정'))
    handle_event(event('book'),s,call);handle_event(event('book'),s,call)
    assert call.call_count==1 and not s['ack']['ok']


@pytest.mark.parametrize('action',sorted(MUTATIONS))
def test_mutation_dispatch(action):
    s={'token':'T'};call=Mock(return_value={'ok':True})
    payload={'id':'reservation-id'}
    handle_event(event(action,payload),s,call)
    call.assert_called_once_with(action,payload)
    assert s['ack']['ok']


def test_pending_is_not_described_as_confirmed():
    s={'token':'T'};handle_event(event('book'),s,Mock(return_value={'state':'pending'}))
    assert '승인' in s['ack']['message']


@pytest.mark.parametrize('action',['book','save_rule','save_prices','admin_bookings','refresh'])
def test_unauthenticated_intents_blocked(action):
    s={};call=Mock();handle_event(event(action),s,call)
    call.assert_not_called();assert not s['ack']['ok']


@pytest.mark.parametrize('d',['bad','1999-01-01','2099-01-01'])
def test_bad_navigation_leaves_current_day(d):
    today=now_kst().date().isoformat();s={'token':'T','day':today}
    handle_event(event('navigate',{'day':d}),s,Mock())
    assert s['day']==today and not s['ack']['ok']


def test_navigation_valid():
    d=(now_kst().date()+timedelta(days=1)).isoformat();s={'token':'T'}
    handle_event(event('navigate',{'day':d}),s,Mock())
    assert s['day']==d and s['ack']['ok']


def test_logout_clears_private_cache_and_token():
    s={'token':'SECRET','kind':'customer','code':'A1','view_data':{'bookings':['PRIVATE']}}
    handle_event(event('logout'),s,Mock(return_value={'ok':True}))
    assert not any(k in s for k in ('token','kind','code','view_data'))


@pytest.mark.parametrize('kind',['customer','admin'])
def test_view_data_strips_private_fields(kind):
    s={'token':'SECRET','kind':kind,'code':'A1'}
    def call(a,p=None):
        if a=='calendar':return {'rules':[],'bookings':[{'starts_at':'T','ends_at':'U','state':'confirmed','name':'OTHER SECRET','customer_hash':'HASH'}],'open_min':600,'close_min':1200}
        if a in ('my_bookings','admin_bookings'):return {'bookings':[{'id':'1','name':'OWN','comment':'own note','customer_hash':'HASH','token':'SECRET','starts_at':'T','ends_at':'U'}]}
        if a=='prices':return {'menu':[{'label':'커트','price':15000}]}
        if a=='admin_price_rules':return {'rules':[]}
        raise AssertionError(a)
    d=get_view_data(s,lambda k,v:v,call)
    assert 'SECRET' not in str(d) and 'HASH' not in str(d)
    assert 'name' not in d['calendar']['bookings'][0]
    assert d['bookings'][0]['name']=='OWN'
    assert d['menu'][0]['price']==15000


def test_start_page_does_not_read_db():
    call=Mock();d=get_view_data({},lambda k,v:v,call)
    assert not d['kind'];call.assert_not_called()
