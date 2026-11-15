from unittest.mock import patch
import pytest
from salon import db
from test_app import make_app, button, assert_clean
from test_db import fake


def test_secret_key_uses_apikey_not_bearer(fake):
    st,post=fake
    st.secrets['SUPABASE_SECRET_KEY']='sb_secret_test_only'
    db.call('session')
    headers=post.call_args.kwargs['headers']
    assert headers['apikey']=='sb_secret_test_only'
    assert 'Authorization' not in headers


@pytest.mark.parametrize('url',[
    'http://example.supabase.co','https://example.supabase.co.attacker.test',
    'https://example.supabase.co@attacker.test','https://example.supabase.co/extra',
])
def test_reject_wrong_supabase_url(fake,url):
    st,post=fake; st.secrets['SUPABASE_URL']=url
    with pytest.raises(db.AppError):
        db.call('session')
    post.assert_not_called()


def test_admin_repeat_and_save():
    at,rpc,calls=make_app(admin=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); button(at,'10:00 · 예약 가능').click().run()
        button(at,'매주 반복').click().run(); assert_clean(at)
        assert len([x for x in at.toggle if x.label.endswith('요일')])==7
        button(at,'시간 설정 저장').click().run(); assert_clean(at)
        saved=next(p for a,p in calls if a=='save_rule')
        assert saved['repeats'] is True
        assert saved['end_date'] is None
        assert len(saved['weekdays'])==1


def test_admin_last_slot_dialog():
    at,rpc,_=make_app(admin=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); button(at,'19:30 · 예약 가능').click().run(); assert_clean(at)
        assert next(x for x in at.number_input if x.label=='설정 길이 (분)').value==30


def test_admin_price_edit_and_save():
    at,rpc,calls=make_app(admin=True)
    with patch('salon.db.call',side_effect=rpc):
        at.run(); button(at,'가격 수정').click().run()
        next(b for b in at.button if b.key and b.key.startswith('date_')).click().run()
        button(at,'＋ 시술 추가').click().run(); assert_clean(at)
        labels=[x for x in at.text_input if x.label=='시술 이름']
        labels[-1].input('어린이 커트').run(); assert_clean(at)
        prices=[x for x in at.number_input if x.label=='가격 (₩ 원)']
        prices[-1].set_value(12000).run(); assert_clean(at)
        button(at,'가격 저장').click().run(); assert_clean(at)
        saved=next(p for a,p in calls if a=='save_prices')
        assert saved['menu'][-1]=={'label':'어린이 커트','price':12000}
