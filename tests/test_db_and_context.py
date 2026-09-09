from app.context.context import ConversationContext, ConversationStatus
from app.context.manager import ContextManager
from support_agent_db.database import Database


def test_database_initialization_and_crud(tmp_path):
    db_path = tmp_path / "test_agent.db"
    db = Database(db_path=db_path)
    db.initialize()

    # User creation
    user_id = db.create_user(name="Test User", external_id="ext_001")
    assert user_id > 0

    # Conversation and Request creation
    req_id = db.create_request(user_id=user_id, question="1С вылетает при проведении")
    assert req_id > 0

    db.complete_request(
        request_id=req_id,
        answer="Проверьте журнал событий.",
        status="success",
        confidence=0.95,
        response_time_ms=1200,
    )

    summary = db.dashboard_summary()
    assert summary["total_requests"] == 1
    assert summary["successful_requests"] == 1


def test_context_manager_updates():
    ctx = ConversationContext()
    mgr = ContextManager(ctx)

    mgr.update_problem("Ошибка при проведении накладной")
    mgr.update_configuration("1С:Управление торговлей")
    mgr.update_configuration_version("11.5.8.200")
    mgr.set_hypothesis("Недостаточно прав у пользователя", confidence=0.85)

    assert ctx.problem == "Ошибка при проведении накладной"
    assert ctx.configuration == "1С:Управление торговлей"
    assert ctx.configuration_version == "11.5.8.200"
    assert ctx.current_hypothesis == "Недостаточно прав у пользователя"
    assert ctx.hypothesis_confidence == 0.85

    mgr.escalate("Требуется вмешательство администратора")
    assert ctx.status == ConversationStatus.ESCALATED
    assert ctx.escalation_reason == "Требуется вмешательство администратора"
