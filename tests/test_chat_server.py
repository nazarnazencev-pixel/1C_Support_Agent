from fastapi.testclient import TestClient

from app.api import chat_server


def test_post_message_routes_through_session_manager(monkeypatch):
    client = TestClient(chat_server.app)

    calls = {}

    def fake_ask(session_id, message):
        calls["session_id"] = session_id
        calls["message"] = message
        return "Ответ агента"

    monkeypatch.setattr(
        chat_server.session_manager,
        "ask",
        fake_ask,
    )

    response = client.post(
        "/api/chat/sess-1",
        json={"message": "Привет"},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "Ответ агента"}
    assert calls == {
        "session_id": "sess-1",
        "message": "Привет",
    }


def test_post_message_rejects_empty_message():
    client = TestClient(chat_server.app)

    response = client.post(
        "/api/chat/sess-1",
        json={"message": "   "},
    )

    assert response.status_code == 400


def test_get_greeting_routes_through_session_manager(monkeypatch):
    client = TestClient(chat_server.app)

    monkeypatch.setattr(
        chat_server.session_manager,
        "get_greeting",
        lambda session_id: f"Здравствуйте, {session_id}!",
    )

    response = client.post("/api/chat/sess-2/greeting")

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Здравствуйте, sess-2!"
    }


def test_feedback_returns_404_for_unknown_session(monkeypatch):
    client = TestClient(chat_server.app)

    monkeypatch.setattr(
        chat_server.session_manager,
        "get",
        lambda session_id: None,
    )

    response = client.post(
        "/api/chat/unknown-session/feedback",
        json={"rating": 8},
    )

    assert response.status_code == 404
