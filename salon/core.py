"""Pure calendar logic. All dates/times are Asia/Seoul; 30-minute, one-chair slots."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
STATE_LABEL = {'available':'예약 가능', 'tentative':'확인 필요', 'unavailable':'예약 불가',
               'confirmed':'예약 확정', 'pending':'승인 대기', 'cancelled':'취소', 'rejected':'반려', 'past':'지난 시간'}
COLORS = {'available':'#DDF2E9','tentative':'#FFF0C2','unavailable':'#E8EBEF',
          'confirmed':'#DBEAFE','pending':'#FFF0C2','past':'#F1F2F4'}

def now_kst():
    return datetime.now(KST)

def monday(day):
    return day-timedelta(days=day.weekday())

def parse_dt(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(KST)

def slot_dt(day, minute):
    return datetime.combine(day, time(minute//60, minute%60), KST)

def hhmm(minute):
    return f'{minute//60:02}:{minute%60:02}'

def schedule_state(day, minute, rules):
    matches=[]
    for rule in rules:
        start=date.fromisoformat(rule['start_date'])
        end=date.fromisoformat(rule['end_date']) if rule.get('end_date') else None
        if start<=day and (end is None or day<=end) and day.isoweekday() in rule['weekdays'] and rule['start_min']<=minute<rule['end_min']:
            matches.append(rule)
    if not matches:
        return 'available'
    # One-date overrides always beat a recurring rule; newest ID wins within type.
    return sorted(matches,key=lambda r:(bool(r['repeats']),-r['id']))[0]['state']

def slot_state(day, minute, calendar):
    dt=slot_dt(day,minute)
    for booking in calendar['bookings']:
        if parse_dt(booking['starts_at'])==dt:
            return booking['state']
    if dt<=parse_dt(calendar['server_now']):
        return 'past'
    return schedule_state(day,minute,calendar['rules'])

def validate_menu(menu):
    if not 1<=len(menu)<=20:
        raise ValueError('가격 항목은 1~20개입니다.')
    labels=[]
    result=[]
    for item in menu:
        label=str(item['label']).strip()
        price=int(item['price'])
        if not 1<=len(label)<=30 or not 0<=price<=10_000_000:
            raise ValueError('시술명과 가격을 확인해 주세요.')
        labels.append(label)
        result.append({'label':label,'price':price})
    if len(set(labels))!=len(labels):
        raise ValueError('시술 이름은 서로 다르게 입력해 주세요.')
    return result
