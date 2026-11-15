from types import SimpleNamespace
from unittest.mock import Mock
import requests
import pytest
from salon import db


class State(dict):
    def __getattr__(self,key):
        return self[key]
    def __setattr__(self,key,value):
        self[key]=value


@pytest.fixture
def fake(monkeypatch):
    state=State(token='private-token',kind='customer',pin='123456',code='A1')
    streamlit=SimpleNamespace(secrets={
        'SUPABASE_URL':'https://demo.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'eyJ.fake.server.key',
        'AUTH_PEPPER':'b'*64},session_state=state,context=SimpleNamespace(ip_address='192.0.2.20'))
    monkeypatch.setattr(db,'st',streamlit)
    post=Mock(return_value=SimpleNamespace(ok=True,json=lambda:{'ok':True},status_code=200))
    monkeypatch.setattr(db.requests,'post',post)
    return streamlit,post


def test_server_side_request(fake):
    _,post=fake
    assert db.call('prices',{'day':'2030-01-07'})=={'ok':True}
    args=post.call_args
    assert args.args[0]=='https://demo.supabase.co/rest/v1/rpc/salon_api'
    assert args.kwargs['json']['token']=='private-token'
    assert args.kwargs['headers']['Authorization']=='Bearer eyJ.fake.server.key'


def test_client_id_hashed_and_stable(fake):
    assert len(db.client_id())==64
    assert db.client_id()==db.client_id()
    assert db.client_id()!='192.0.2.20'


def test_authentication_omits_current_token(fake):
    _,post=fake
    db.call('login',{'code':'A1','pin':'123456'},False)
    assert post.call_args.kwargs['json']['token']==''
    assert len(post.call_args.kwargs['json']['payload']['client'])==64


def test_expiry_clears_access(fake):
    st,post=fake
    post.return_value.json=lambda:{'error':'만료','expired':True}
    with pytest.raises(db.AppError,match='만료'):
        db.call('calendar')
    assert 'token' not in st.session_state
    assert 'pin' not in st.session_state
    assert st.session_state.auth_expired


def test_network_error_never_retried(fake):
    _,post=fake
    post.side_effect=requests.Timeout('response lost')
    with pytest.raises(db.AppError,match='예약 내역'):
        db.call('book')
    assert post.call_count==1


def test_internal_error_hidden(fake):
    _,post=fake
    post.return_value=SimpleNamespace(ok=False,status_code=500,text='sensitive SQL internal')
    with pytest.raises(db.AppError) as exc:
        db.call('calendar')
    assert 'sensitive' not in str(exc.value)
    assert '500' in str(exc.value)


def test_app_error_passed_through(fake):
    _,post=fake
    post.return_value.json=lambda:{'error':'이미 예약된 시간입니다.'}
    with pytest.raises(db.AppError,match='이미 예약된'):
        db.call('book')
