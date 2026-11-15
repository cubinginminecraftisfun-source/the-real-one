"""Read-only HTML calendar: no personal data, scripts, links or access tokens."""
from datetime import timedelta
from html import escape
from .core import COLORS, STATE_LABEL, hhmm, slot_state

CSS='''<style>
:root{--primary:#126A52;--ink:#173C34;--muted:#526960}
.stApp{background:#F6F8F7;color:#173C34;font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
.block-container{max-width:850px;padding-top:1.5rem;padding-bottom:4rem}
header[data-testid="stHeader"]{background:transparent}
#MainMenu,footer{visibility:hidden}
h1{font-size:2rem!important;letter-spacing:-.06em} h2{font-size:1.4rem!important}
h3{font-size:1.12rem!important}
.stButton>button,.stDownloadButton>button{min-height:48px;border-radius:15px;font-weight:650;border:1px solid #D6E0DC;white-space:normal}
.stButton>button[kind="primary"]{background:#126A52;color:white;border-color:#126A52}
.stTextInput input,.stTextArea textarea,.stNumberInput input{font-size:16px!important}
.hero{padding:28px 22px;background:#E4F0EA;border-radius:24px;margin:12px 0 24px}
.eyebrow{letter-spacing:.16em;font-size:12px;font-weight:750;color:#356252}
.hero h1{margin:12px 0}.hero p{color:#365C50;line-height:1.8;margin-bottom:0}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin:12px 0;color:#39554A}
.legend span{padding:5px 9px;border-radius:8px;border:1px solid #D8E1DC}
.week-scroll{overflow-x:auto;border:1px solid #D6E0DC;border-radius:16px;background:white;margin:12px 0;-webkit-overflow-scrolling:touch}
.week-grid{display:grid;grid-template-columns:48px repeat(7,minmax(78px,1fr));min-width:605px;padding:8px;gap:4px}
.week-grid .head{text-align:center;font-size:12px;padding:8px 0;font-weight:750;line-height:1.6}
.week-grid .time{font-size:11px;align-self:center;color:#526960}
.week-grid .cell{font-size:11px;min-height:34px;display:flex;align-items:center;justify-content:center;border-radius:7px;color:#18382E}
.st-key-date_strip [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:3px!important}
.st-key-date_strip [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:0!important}
.st-key-date_strip button{padding:4px 0!important;font-size:12px!important;min-height:52px}
@media(max-width:600px){.block-container{padding-left:14px;padding-right:14px;padding-top:1rem}h1{font-size:1.7rem!important}.hero{padding:22px 18px}.st-key-slot_grid [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important}.st-key-slot_grid [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:0!important}}
</style>'''

def week_html(start,calendar):
    days=[start+timedelta(days=i) for i in range(7)]
    headers='<div class="head">시간</div>'+''.join(f'<div class="head">{d.month}/{d.day}<br>{"월화수목금토일"[d.weekday()]}</div>' for d in days)
    cells=[]
    short={'available':'가능','tentative':'확인 필요','unavailable':'불가','confirmed':'예약됨','pending':'승인 대기','past':'지난 시간'}
    for minute in range(calendar['open_min'],calendar['close_min'],30):
        cells.append(f'<div class="time">{hhmm(minute)}</div>')
        for day in days:
            state=slot_state(day,minute,calendar)
            cells.append(f'<div class="cell" style="background:{COLORS[state]}" title="{escape(STATE_LABEL[state])}">{short[state]}</div>')
    return '<div class="week-scroll"><div class="week-grid">'+headers+''.join(cells)+'</div></div>'
