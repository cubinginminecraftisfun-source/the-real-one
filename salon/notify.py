"""Optional Telegram alert to the shop owner when a customer saves a booking.

Best-effort only: a missing setting, network error or Telegram outage must NEVER affect the booking.
The bot token lives only in Streamlit server-side secrets; it is never sent to the browser iframe.
"""
import threading
import requests
import streamlit as st
from .core import parse_dt

WEEKDAYS = '월화수목금토일'


def format_booking(payload, state):
    """Plain text (no parse_mode), so customer-typed names/comments cannot inject markup."""
    start = parse_dt(str(payload['starts_at']))
    end = parse_dt(str(payload['ends_at']))
    status = '승인 필요' if state == 'pending' else '확정'
    lines = [
        f'📅 새 예약 ({status})',
        f"이름: {str(payload.get('name', '')).strip()[:30]}",
        f'일시: {start:%m/%d}({WEEKDAYS[start.weekday()]}) {start:%H:%M}–{end:%H:%M}',
        f"시술: {payload.get('service_label', '')} (₩{int(payload.get('expected_price', 0)):,})",
    ]
    comment = str(payload.get('comment', '')).strip()
    if comment:
        lines.append(f'요청: {comment[:100]}')
    return '\n'.join(lines)


def _post(token, chat_id, text):
    try:
        requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                      json={'chat_id': chat_id, 'text': text}, timeout=(3, 5))
    except requests.RequestException:
        pass  # never retry or raise: the booking is already saved


def send(text):
    # API KEY HERE: read secrets on the Streamlit script thread, then send in the background
    # so a slow Telegram never delays the customer's booking confirmation.
    try:
        token = str(st.secrets.get('TELEGRAM_BOT_TOKEN', '') or '')
        chat_id = str(st.secrets.get('TELEGRAM_CHAT_ID', '') or '')
    except Exception:
        return
    if not token or not chat_id or 'API KEY HERE' in token or 'API KEY HERE' in chat_id:
        return
    threading.Thread(target=_post, args=(token, chat_id, text), daemon=True).start()
