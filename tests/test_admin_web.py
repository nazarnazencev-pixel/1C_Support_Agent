from fastapi.testclient import TestClient

from app.admin import web as admin_web
from app.admin.web import _render_escalation_row


def test_render_escalation_row_escapes_html():
    row = _render_escalation_row(
        {
            "escalation_id": 1,
            "user_name": "<b>Иван</b>",
            "question": "<script>alert(1)</script>",
            "reason": "Низкая уверенность & риск",
            "confidence": 0.42,
        }
    )

    assert "<script>" not in row
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in row
    assert "&lt;b&gt;Иван&lt;/b&gt;" in row
    assert "&amp;" in row


def test_dashboard_html_escapes_user_supplied_fields(monkeypatch):
    monkeypatch.setattr(
        admin_web.panel,
        "get_dashboard_summary",
        lambda: {
            "total_requests": 1,
            "success_rate_percent": 0,
            "avg_rating_0_10": 0,
            "escalated_requests": 1,
            "avg_response_time_ms": 0,
        },
    )
    monkeypatch.setattr(
        admin_web.panel,
        "get_open_escalations",
        lambda: [
            {
                "escalation_id": 1,
                "user_name": "Тест",
                "question": "<img src=x onerror=alert(1)>",
                "reason": "Низкая уверенность",
                "confidence": 0.3,
            }
        ],
    )

    client = TestClient(admin_web.app)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "<img src=x onerror=alert(1)>" not in response.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in response.text
