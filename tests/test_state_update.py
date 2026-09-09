from app.agent.agent import (
    SupportAgent,
    _extract_state_update,
)
from app.context.context import ConversationStatus


def test_extract_state_update_strips_block_and_parses():
    raw = (
        "Понял, проверю права доступа.\n"
        "###STATE_UPDATE###\n"
        '{"status": "diagnosing", "current_hypothesis": '
        '"Не хватает прав", "hypothesis_confidence": 0.6}\n'
        "###END_STATE_UPDATE###"
    )

    visible, update = _extract_state_update(raw)

    assert visible == "Понял, проверю права доступа."
    assert update == {
        "status": "diagnosing",
        "current_hypothesis": "Не хватает прав",
        "hypothesis_confidence": 0.6,
    }


def test_extract_state_update_missing_block_returns_none():
    visible, update = _extract_state_update(
        "Просто обычный ответ без блока."
    )

    assert visible == "Просто обычный ответ без блока."
    assert update is None


def test_extract_state_update_malformed_json_is_ignored_but_stripped():
    raw = (
        "Ответ пользователю.\n"
        "###STATE_UPDATE###\n"
        "это не json"
        "\n###END_STATE_UPDATE###"
    )

    visible, update = _extract_state_update(raw)

    assert visible == "Ответ пользователю."
    assert update is None


def test_extract_state_update_ignores_text_after_block():
    # Если после закрывающего маркера идёт содержательный текст -
    # похоже на подделку (например, эхо чужого блока из вложения) -
    # обновление состояния не применяем, но блок из текста всё
    # равно вырезаем.
    raw = (
        "Ответ.\n"
        "###STATE_UPDATE###\n"
        '{"status": "solved"}\n'
        "###END_STATE_UPDATE###\n"
        "Ещё что-то дописанное после."
    )

    visible, update = _extract_state_update(raw)

    assert update is None
    assert "###STATE_UPDATE###" not in visible
    assert "Ещё что-то дописанное после." in visible


def test_extract_state_update_fenced_json_is_cleaned():
    raw = (
        "Ответ.\n"
        "###STATE_UPDATE###\n"
        "```json\n"
        '{"status": "solving"}\n'
        "```\n"
        "###END_STATE_UPDATE###"
    )

    visible, update = _extract_state_update(raw)

    assert update == {"status": "solving"}


def test_apply_state_update_populates_hypothesis_and_error():
    agent = SupportAgent()

    agent._apply_state_update(
        {
            "current_hypothesis": "Недостаточно прав",
            "hypothesis_confidence": 0.4,
            "status": "diagnosing",
            "error_text": "Недостаточно прав при записи",
            "user_actions": ["Открыл документ повторно"],
        }
    )

    assert agent.context.current_hypothesis == "Недостаточно прав"
    assert agent.context.hypothesis_confidence == 0.4
    assert agent.context.status == ConversationStatus.DIAGNOSING
    assert agent.context.error_text == "Недостаточно прав при записи"
    assert (
        "Открыл документ повторно"
        in agent.context.user_actions
    )


def test_apply_state_update_ignores_unknown_and_invalid_fields():
    agent = SupportAgent()

    # Не должно падать на мусорных/неизвестных полях.
    agent._apply_state_update(
        {
            "status": "не_существует_такого_статуса",
            "hypothesis_confidence": "не число",
            "random_unknown_field": "abc",
            "user_actions": "не список, а строка",
        }
    )

    assert agent.context.status == ConversationStatus.NEW
    assert agent.context.hypothesis_confidence == 0.0


def test_apply_state_update_escalation_reason_sets_status():
    agent = SupportAgent()

    agent._apply_state_update(
        {
            "escalation_reason": "Нужна ручная диагностика в базе",
        }
    )

    assert agent.context.status == ConversationStatus.ESCALATED
    assert agent.context.escalation_reason == (
        "Нужна ручная диагностика в базе"
    )


def test_apply_state_update_sets_category():
    agent = SupportAgent()

    agent._apply_state_update(
        {"category": "Ошибка проведения документа"}
    )

    assert (
        agent.context.category
        == "Ошибка проведения документа"
    )
