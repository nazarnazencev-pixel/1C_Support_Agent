import pytest
from unittest.mock import MagicMock
from app.session.session import Session, OPERATOR_CONNECTING_MESSAGE
from app.session.redis_session import RedisSessionManager
from app.admin.panel import AdminPanel
from support_agent_db.database import Database


def test_low_confidence_escalation(tmp_path):
    db_path = tmp_path / "test_escalation.db"
    db = Database(db_path=db_path)
    db.initialize()

    session = Session(session_id="user_low_confidence", confidence_threshold=0.80)
    session.db = db

    # Имитируем ответ агента с низкой уверенностью (0.5)
    session.agent.ask = MagicMock(return_value="Предположительный ответ")
    session.agent.context.set_hypothesis("Гипотеза 1", confidence=0.50)

    answer = session.ask("1С выдаёт неизвестную ошибку")

    assert answer == OPERATOR_CONNECTING_MESSAGE
    assert session.agent.context.status.value == "escalated"


def test_csat_feedback_recording(tmp_path):
    db_path = tmp_path / "test_csat.db"
    db = Database(db_path=db_path)
    db.initialize()

    session = Session(session_id="user_csat")
    session.db = db

    session.agent.ask = MagicMock(return_value="Ответ поддержки")
    session.agent.context.set_hypothesis("Гипотеза 1", confidence=0.90)

    session.ask("Как выгрузить отчет?")

    # Пользователь ставит 9 из 10
    feedback_id = session.submit_csat_feedback(rating=9, comment="Отлично помогли!")
    assert feedback_id is not None

    panel = AdminPanel(db=db)
    csat = panel.get_user_satisfaction()
    assert csat["total_feedbacks"] == 1
    assert csat["avg_rating_0_10"] == 9.0


def test_admin_panel_metrics(tmp_path):
    db_path = tmp_path / "test_panel.db"
    db = Database(db_path=db_path)
    db.initialize()

    panel = AdminPanel(db=db)
    summary = panel.get_dashboard_summary()

    assert "total_requests" in summary
    assert "csat_percent" in summary
    assert "session_metrics" in summary


def test_redis_session_manager_fallback():
    manager = RedisSessionManager(redis_host="localhost", redis_port=9999)
    session = manager.get_or_create("test_session_id")
    assert session.session_id == "test_session_id"


def test_redis_session_serialization_and_hydration():
    manager = RedisSessionManager(redis_host="localhost", redis_port=9999)
    mock_redis = MagicMock()
    manager.redis_client = mock_redis

    session = Session(session_id="session_redis_test")
    session.agent.get_greeting()
    session.agent.context.problem = "Проблема с лицензией 1С"

    # Сохраняем состояние
    manager.save_session_state(session)
    mock_redis.setex.assert_called_once()

    # Имитируем гидрацию в другом экземпляре
    mock_redis.get.return_value = '{"session_id": "session_redis_test", "created_at": 1000, "last_activity": 1005, "history": [{"role": "assistant", "content": "Привет"}], "context": {"problem": "Проблема с лицензией 1С"}}'

    manager2 = RedisSessionManager(redis_host="localhost", redis_port=9999)
    manager2.redis_client = mock_redis

    restored_session = manager2.get_or_create("session_redis_test")
    assert restored_session.session_id == "session_redis_test"
    assert restored_session.agent.context.problem == "Проблема с лицензией 1С"
    assert len(restored_session.agent.history) == 1


def test_redis_session_restores_full_context_including_status():
    """
    Раньше _hydrate_session_from_redis восстанавливал только 4 поля
    контекста (problem, configuration, current_hypothesis,
    hypothesis_confidence) - status и всё остальное терялись, хотя
    save_session_state через to_dict() сохраняет всё.
    """

    manager = RedisSessionManager(redis_host="localhost", redis_port=9999)
    mock_redis = MagicMock()
    manager.redis_client = mock_redis

    session = Session(session_id="session_full_restore")
    session.agent.context.update_problem("1С не открывается")
    session.agent.context.update_category("Технический сбой платформы")
    session.agent.context.add_completed_check("Проверена версия платформы")
    session.agent.context.escalate("Требуется ручная диагностика")

    manager.save_session_state(session)

    saved_json = mock_redis.setex.call_args[0][2]
    mock_redis.get.return_value = saved_json

    manager2 = RedisSessionManager(redis_host="localhost", redis_port=9999)
    manager2.redis_client = mock_redis

    restored = manager2.get_or_create("session_full_restore")

    assert restored.agent.context.status.value == "escalated"
    assert restored.agent.context.problem == "1С не открывается"
    assert restored.agent.context.category == "Технический сбой платформы"
    assert (
        "Проверена версия платформы"
        in restored.agent.context.completed_checks
    )
    assert (
        restored.agent.context.escalation_reason
        == "Требуется ручная диагностика"
    )
