from datetime import date
import pytest
from salon.core import (KST, hhmm, monday, parse_dt, schedule_state, slot_dt,
                        slot_state, validate_menu)
from salon.ui import week_html

DAY=date(2030,1,7)  # Monday

def rule(id=1,state='unavailable',repeats=True,**kwargs):
    return dict(id=id,state=state,repeats=repeats,start_date='2030-01-01',
                end_date=None,weekdays=[1],start_min=600,end_min=660,**kwargs)


def test_monday():
    assert monday(date(2030,1,13))==DAY


def test_timezone():
    assert parse_dt('2030-01-07T01:00:00Z')==slot_dt(DAY,600)
    assert str(slot_dt(DAY,600).tzinfo)=='Asia/Seoul'


def test_hhmm():
    assert hhmm(1170)=='19:30'


def test_default_available():
    assert schedule_state(DAY,600,[])=='available'


def test_rule_boundaries():
    rules=[rule()]
    assert schedule_state(DAY,599,rules)=='available'
    assert schedule_state(DAY,600,rules)=='unavailable'
    assert schedule_state(DAY,659,rules)=='unavailable'
    assert schedule_state(DAY,660,rules)=='available'


def test_weekday_match():
    assert schedule_state(date(2030,1,8),600,[rule()])=='available'


def test_one_date_beats_newer_repeat():
    exact=rule(id=1,state='available',repeats=False)
    exact.update(start_date='2030-01-07',end_date='2030-01-07')
    assert schedule_state(DAY,600,[exact,rule(id=999)])=='available'


def test_latest_within_type_wins():
    assert schedule_state(DAY,600,[rule(),rule(id=2,state='tentative')])=='tentative'


def test_rule_expired():
    old=rule(); old['end_date']='2030-01-06'
    assert schedule_state(DAY,600,[old])=='available'


def test_booking_beats_unavailability():
    cal={'bookings':[{'starts_at':'2030-01-07T01:00:00Z','state':'confirmed'}],
         'rules':[rule()],'server_now':'2030-01-01T00:00:00Z'}
    assert slot_state(DAY,600,cal)=='confirmed'


def test_past_slot():
    cal={'bookings':[],'rules':[],'server_now':'2030-01-07T02:00:00Z'}
    assert slot_state(DAY,600,cal)=='past'


def test_menu_normalization():
    assert validate_menu([{'label':' 남성 커트 ','price':15000}])==[{'label':'남성 커트','price':15000}]


@pytest.mark.parametrize('menu',[
    [],[{'label':'','price':100}], [{'label':'컷','price':-1}],
    [{'label':'컷','price':10000001}],
    [{'label':'컷','price':100},{'label':' 컷 ','price':200}],
    [{'label':'x'*31,'price':100}],
])
def test_bad_menus(menu):
    with pytest.raises(ValueError):
        validate_menu(menu)


def test_week_html_contains_no_personal_data():
    cal={'bookings':[{'starts_at':'2030-01-07T01:00:00Z','state':'confirmed','name':'PRIVATE_NAME','comment':'PRIVATE_COMMENT'}],
         'rules':[],'server_now':'2030-01-01T00:00:00Z','open_min':600,'close_min':1200}
    html=week_html(DAY,cal)
    assert 'PRIVATE_NAME' not in html and 'PRIVATE_COMMENT' not in html
    assert '예약됨' in html
    assert html.count('class="cell"')==20*7
    assert '<script' not in html
