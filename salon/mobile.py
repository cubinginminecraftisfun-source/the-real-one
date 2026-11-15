"""V2 mobile view adapter. Reuses salon.db.call and the existing salon_api RPC.
Never sends a Supabase secret, login token or customer ownership hash to the iframe.
"""
from datetime import date, timedelta
from . import db
from .core import now_kst, monday

MUTATIONS = {'book','save_rule','save_prices','reset_prices','delete_rule','decide','cancel',
             'change_password','delete_price_rule'}
MESSAGES = {'book':'예약을 저장했습니다.','save_rule':'시간 설정을 저장했습니다.',
            'save_prices':'가격표를 저장했습니다.','change_password':'비밀번호를 변경했습니다.',
            'cancel':'예약을 취소했습니다.','decide':'예약을 처리했습니다.',
            'delete_rule':'시간 설정을 삭제했습니다.','delete_price_rule':'반복 가격을 삭제했습니다.',
            'reset_prices':'이 날짜의 특별 가격을 해제했습니다.'}


def handle_event(event, state, call=db.call):
    """At-most-once per session/event id, including errors and uncertain network outcomes."""
    if not isinstance(event,dict) or not isinstance(event.get('id'),str):
        return
    event_id=event['id']
    if len(event_id)>128 or event_id in state.get('seen_events',[]):
        return
    state['seen_events']=(state.get('seen_events',[])+[event_id])[-256:]
    state['last_event']=event_id
    action=event.get('action','')
    payload=event.get('payload',{})
    ack={'id':event_id,'action':action,'ok':False,'style':'error'}
    state['ack']=ack
    try:
        if not isinstance(payload,dict):
            raise db.AppError('입력 정보를 확인해 주세요.')
        if action in ('create_session','login'):
            if state.get('token'):
                raise db.AppError('먼저 나가기를 눌러 주세요.')
            result=call(action,payload,authenticated=False)
            state.pop('auth_expired',None)
            state.pop('view_data',None)
            for key in ('token','kind','code','expires_at'):
                state[key]=result.get(key)
            state['day']=now_kst().date().isoformat()
            ack.update(ok=True,style='success',message='접속했습니다.')
        elif not state.get('token'):
            raise db.AppError('시작 화면에서 접속해 주세요.')
        elif action=='navigate':
            value=date.fromisoformat(str(payload.get('day','')))
            today=now_kst().date()
            if not today-timedelta(days=7)<=value<=today+timedelta(days=90):
                raise db.AppError('선택할 수 없는 날짜입니다.')
            state['day']=value.isoformat();ack.update(ok=True)
        elif action=='refresh':
            ack.update(ok=True)
        elif action=='logout':
            call('logout')
            for key in ('token','kind','code','expires_at','view_data'):
                state.pop(key,None)
            ack.update(ok=True,style='success',message='시작 화면으로 이동했습니다.')
        elif action in MUTATIONS:
            result=call(action,payload)
            msg=MESSAGES[action]
            if result.get('state')=='pending':
                msg='예약을 요청했습니다. 매장 승인을 기다려 주세요.'
            ack.update(ok=True,style='success',message=msg)
        else:
            raise db.AppError('지원하지 않는 작업입니다.')
    except (ValueError,TypeError):
        ack['message']='입력 형식을 확인해 주세요.'
    except db.AppError as exc:
        ack['message']=str(exc)


def get_view_data(state, setting, call=db.call):
    day=date.fromisoformat(state.get('day',now_kst().date().isoformat()))
    data={'shop_name':str(setting('SHOP_NAME','해담살롱')),
          'address':str(setting('SHOP_ADDRESS','매장 주소')),
          'phone':str(setting('SHOP_PHONE','02-000-0000')),
          'kind':state.get('kind') if state.get('token') else None,
          'code':state.get('code'),'day':day.isoformat()}
    if not data['kind']:
        return data
    start=monday(day)
    calendar=call('calendar',{'from':start.isoformat()})
    admin=data['kind']=='admin'
    bookings=call('admin_bookings',{'from':start.isoformat()}) if admin else call('my_bookings')
    menu=call('prices',{'day':day.isoformat()})
    # Explicit allowlist strips tokens/customer_hash even if the RPC ever changes its shape.
    fields=('id','starts_at','ends_at','state','name','comment','service_label','price')
    data['bookings']=[{k:b[k] for k in fields if k in b} for b in bookings.get('bookings',[])]
    data['calendar']={k:calendar.get(k) for k in ('rules','open_min','close_min','server_now')}
    data['calendar']['bookings']=[{k:b.get(k) for k in ('starts_at','ends_at','state')}
                                  for b in calendar.get('bookings',[])]
    data['menu']=menu.get('menu',[])
    data['price_rules']=call('admin_price_rules').get('rules',[]) if admin else []
    return data
