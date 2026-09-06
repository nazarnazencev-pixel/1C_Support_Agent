import pytest
from app.session.session import Session
from app.session.session_manager import SessionManager


def test_session_greeting():
    session = Session(session_id="test_sess_1")
    greeting = session.get_greeting()
    assert "Здравствуйте!" in greeting
    assert "Молвест" in greeting


def test_session_manager():
    sm = SessionManager()
    session = sm.get_or_create("user_abc")
    assert session.session_id == "user_abc"
    assert sm.exists("user_abc")
    
    greeting = sm.get_greeting("user_abc")
    assert "Здравствуйте!" in greeting

    sm.clear()
    assert not sm.exists("user_abc")
