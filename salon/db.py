"""Server-side Supabase RPC. Never embed a service-role secret in HTML or a QR URL."""
import hashlib
import hmac
import secrets
from urllib.parse import urlparse
import requests
import streamlit as st

class AppError(Exception):
    pass


def client_id():
    pepper=str(st.secrets['AUTH_PEPPER'])  # API KEY HERE: random server-only signing secret
    ip=getattr(st.context,'ip_address',None)
    if not ip:
        if 'client_nonce' not in st.session_state:
            st.session_state.client_nonce=secrets.token_hex(24)
        ip=st.session_state.client_nonce
    return hmac.new(pepper.encode(),str(ip).encode(),hashlib.sha256).hexdigest()


def call(action, payload=None, authenticated=True):
    # API KEY HERE: URL and secret key belong ONLY in Streamlit server-side secrets.
    url=str(st.secrets['SUPABASE_URL']).rstrip('/')
    key=str(st.secrets.get('SUPABASE_SECRET_KEY') or st.secrets.get('SUPABASE_SERVICE_ROLE_KEY',''))
    parsed=urlparse(url)
    if (parsed.scheme!='https' or not (parsed.hostname or '').endswith('.supabase.co')
        or parsed.path not in ('','/') or parsed.username or parsed.password
        or parsed.query or parsed.fragment or not key or 'API KEY HERE' in key):
        raise AppError('Supabase 연결 설정을 확인해 주세요. 시작 안내서를 참고해 주세요.')
    headers={'apikey':key,'Content-Type':'application/json'}
    # sb_secret_ keys are NOT JWTs. Send them only as apikey, never as Bearer JWT.
    if not key.startswith('sb_secret_'):
        headers['Authorization']='Bearer '+key
    data=dict(payload or {})
    if action in ('create_session','login'):
        data['client']=client_id()
    try:
        response=requests.post(
            url+'/rest/v1/rpc/salon_api',
            headers=headers,
            json={'action':action,'payload':data,'token':st.session_state.get('token','') if authenticated else ''},
            timeout=(5,20),
        )
    except requests.RequestException as exc:
        # Never automatically retry writes: a response can be lost after a successful commit.
        raise AppError('연결이 불안정합니다. 예약 내역을 먼저 확인한 뒤 다시 시도해 주세요.') from exc
    if not response.ok:
        # Do not expose internal DB details / SQL errors / secrets to customers.
        raise AppError(f'데이터 요청에 실패했습니다 (HTTP {response.status_code}). 관리자에게 문의해 주세요.')
    try:
        result=response.json()
    except ValueError as exc:
        raise AppError('서버 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.') from exc
    if not isinstance(result,dict):
        raise AppError('데이터베이스 초기 설정을 확인해 주세요.')
    if result.get('expired'):
        for field in ('token','kind','pin','code','expires_at'):
            st.session_state.pop(field,None)
        st.session_state.auth_expired=True
    if result.get('error'):
        raise AppError(result['error'])
    return result
