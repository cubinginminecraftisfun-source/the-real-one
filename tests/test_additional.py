from unittest.mock import patch
import pytest
from salon import db
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


