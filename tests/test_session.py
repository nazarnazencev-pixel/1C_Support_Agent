import pytest
from app.session.session import Session, OPERATOR_CONNECTING_MESSAGE
from app.session.session_manager import SessionManager
from app.context.context import ConversationStatus
from support_agent_db.database import Database


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


def test_low_confidence_escalation_end_to_end(monkeypatch):
    """
    Раньше эскалация по низкой уверенности проверялась только тестом,
    который сам вызывал context.set_hypothesis() в обход реального
    кода - то есть ничего не проверял в реальном потоке.

    Здесь мокается только сетевой вызов (SupportAgent._chat) -
    ровно то место, где GigaChat реально отвечает. Всё остальное
    (разбор STATE_UPDATE, заполнение ConversationContext, решение
    Session об эскалации) идёт через настоящий код.
    """

    session = Session(session_id="test_e2e_escalation")

    raw_model_reply = (
        "Возможно, дело в правах доступа, но я не уверен.\n"
        "###STATE_UPDATE###\n"
        '{"current_hypothesis": "Не назначена роль на объект", '
        '"hypothesis_confidence": 0.3}\n'
        "###END_STATE_UPDATE###"
    )

    monkeypatch.setattr(
        session.agent,
        "_chat",
        lambda messages: raw_model_reply,
    )

    answer = session.ask("1С выдаёт неизвестную ошибку")

    assert answer == OPERATOR_CONNECTING_MESSAGE
    assert session.agent.context.status == ConversationStatus.ESCALATED
    assert (
        session.agent.context.current_hypothesis
        == "Не назначена роль на объект"
    )


def test_session_reads_agent_settings_from_db(tmp_path, monkeypatch):
    """
    Раньше agent_settings (confidence_threshold,
    max_knowledge_results, target_response_time_ms) существовали в
    БД, но код их никогда не читал - использовались только
    захардкоженные значения по умолчанию.
    """

    db = Database(db_path=tmp_path / "settings_test.db")
    db.initialize()
    db.set_setting("confidence_threshold", "0.55")
    db.set_setting("max_knowledge_results", "7")
    db.set_setting("target_response_time_ms", "1234")

    monkeypatch.setattr(
        "app.session.session.Database",
        lambda: db,
    )

    session = Session(session_id="settings_test_user")

    assert session.confidence_threshold == 0.55
    assert session.agent.max_knowledge_results == 7
    assert session.target_response_time_ms == 1234


def test_session_explicit_confidence_threshold_overrides_db(
    tmp_path, monkeypatch
):
    db = Database(db_path=tmp_path / "settings_override.db")
    db.initialize()
    db.set_setting("confidence_threshold", "0.55")

    monkeypatch.setattr(
        "app.session.session.Database",
        lambda: db,
    )

    session = Session(
        session_id="settings_override_user",
        confidence_threshold=0.99,
    )

    assert session.confidence_threshold == 0.99


def test_session_falls_back_to_defaults_without_db(monkeypatch):
    def _raise():
        raise RuntimeError("БД недоступна")

    monkeypatch.setattr("app.session.session.Database", _raise)

    session = Session(session_id="no_db_user")

    assert session.db is None
    assert session.confidence_threshold == 0.80
    assert session.agent.max_knowledge_results == 3
    assert session.target_response_time_ms == 5000


def test_session_persists_category_from_state_update(
    tmp_path, monkeypatch
):
    """
    Раньше Database.create_request поддерживал category, но
    Session никогда его не передавал - v_category_stats всегда
    показывал "Без категории".
    """

    db = Database(db_path=tmp_path / "category_test.db")
    db.initialize()

    monkeypatch.setattr(
        "app.session.session.Database",
        lambda: db,
    )

    session = Session(session_id="category_test_user")

    raw_model_reply = (
        "Проверьте права доступа к документу.\n"
        "###STATE_UPDATE###\n"
        '{"category": "Права доступа", '
        '"current_hypothesis": "Нет прав", '
        '"hypothesis_confidence": 0.9}\n'
        "###END_STATE_UPDATE###"
    )

    monkeypatch.setattr(
        session.agent,
        "_chat",
        lambda messages: raw_model_reply,
    )

    session.ask("Не могу провести документ")

    row = db.fetch_one(
        "SELECT category FROM requests WHERE id = ?",
        (session.last_request_id,),
    )

    assert row["category"] == "Права доступа"
