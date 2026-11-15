"""V2 Streamlit entrypoint smoke test: custom iframe internals have separate JS tests."""
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'


def test_start_screen_constructs_component_without_database_call():
    at=AppTest.from_file(str(APP),default_timeout=10)
    at.secrets={'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SECRET_KEY':'sb_secret_test','AUTH_PEPPER':'test'}
    with patch('salon.db.call') as call:
        at.run()
    assert not list(at.exception)
    call.assert_not_called()


def test_missing_config_is_clear_not_a_crash():
    at=AppTest.from_file(str(APP),default_timeout=10)
    at.run()
    assert not list(at.exception)
    assert len(at.error)==1
