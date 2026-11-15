"""Existing salon application, V2 mobile calendar view. Same database and server adapter.
Existing deployments MUST run supabase/migrate_v2.sql, not setup.sql. See UPGRADE_V2.md.
"""
import streamlit as st
from salon import db
from salon.calendar_component import calendar
from salon.mobile import handle_event, get_view_data

st.set_page_config(page_title='미용실 예약',page_icon='✂️',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
:root {color-scheme:light}
html,body,.stApp {background:#fff!important;color:#172b3b!important;overscroll-behavior:none}
header[data-testid="stHeader"],footer,[data-testid="stToolbar"],#MainMenu {display:none!important}
[data-testid="stMain"] {overflow:hidden!important;height:100dvh!important}
[data-testid="stMainBlockContainer"] {padding:0!important;max-width:100%!important;height:100dvh!important}
[data-testid="stVerticalBlock"] {gap:0!important}
iframe[title="salon.calendar_component.salon_mobile_calendar_v2"] {height:100dvh!important;min-height:360px;display:block;border:0}
[data-testid="stElementContainer"]:has(iframe) {height:100dvh!important}
</style>''',unsafe_allow_html=True)


def configured():
    try:
        return bool(st.secrets.get('SUPABASE_URL') and
                    (st.secrets.get('SUPABASE_SECRET_KEY') or st.secrets.get('SUPABASE_SERVICE_ROLE_KEY'))
                    and st.secrets.get('AUTH_PEPPER'))
    except Exception:
        return False


def setting(key,default):
    return st.secrets.get(key,default)


def main():
    if not configured():
        st.error('연결 설정이 필요합니다. Streamlit Secrets를 확인해 주세요.')
        return
    # The iframe only sends intents; it has no database credentials or session token.
    event=st.session_state.get('mobile_calendar')
    handle_event(event,st.session_state)
    try:
        data=get_view_data(st.session_state,setting)
        st.session_state.view_data=data
    except db.AppError as exc:
        cached=st.session_state.get('view_data',{})
        if st.session_state.get('auth_expired'):
            cached={}
        data={**cached,'shop_name':setting('SHOP_NAME','해담살롱'),
              'address':setting('SHOP_ADDRESS',''),'phone':setting('SHOP_PHONE',''),
              'kind':st.session_state.get('kind') if st.session_state.get('token') else None}
        ack=st.session_state.get('ack',{})
        # Do not describe a completed write as failed merely because its follow-up read failed.
        st.session_state.ack={**ack,'message':('저장 후 새로고침에 실패했습니다. 내역을 먼저 확인해 주세요.'
                              if ack.get('ok') and ack.get('action') not in ('navigate','refresh')
                              else str(exc)),'style':'warning' if ack.get('ok') else 'error'}
    calendar(data=data,ack=st.session_state.get('ack'),key='mobile_calendar',default=None)


main()
