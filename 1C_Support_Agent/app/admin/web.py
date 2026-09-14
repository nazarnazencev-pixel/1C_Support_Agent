import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.admin.panel import AdminPanel

app = FastAPI(title="1C Support AI - Admin Dashboard")
panel = AdminPanel()


@app.get("/api/dashboard")
def get_dashboard_summary():
    return panel.get_dashboard_summary()


@app.get("/api/daily-stats")
def get_daily_stats():
    return panel.get_daily_stats()


@app.get("/api/category-stats")
def get_category_stats():
    return panel.get_category_stats()


@app.get("/api/escalations")
def get_escalations():
    return panel.get_open_escalations()


def _render_escalation_row(escalation: dict) -> str:
    """
    Строит одну строку таблицы эскалаций.

    question/user_name/reason - это, в конечном счёте, текст,
    введённый пользователем в чате (question - его сообщение
    напрямую). Без html.escape() пользователь, вписавший в вопрос
    <script>...</script>, выполнил бы произвольный HTML/JS в
    браузере оператора, открывшего дашборд (stored XSS).
    """

    confidence_percent = (
        escalation.get("confidence") or 0
    ) * 100

    escalation_id = html.escape(
        str(escalation.get("escalation_id", ""))
    )
    user_name = html.escape(
        str(escalation.get("user_name", ""))
    )
    question = html.escape(
        str(escalation.get("question", ""))
    )
    reason = html.escape(
        str(escalation.get("reason", ""))
    )

    return (
        "<tr>"
        f"<td>{escalation_id}</td>"
        f"<td>{user_name}</td>"
        f"<td>{question}</td>"
        f"<td><span class='badge'>{reason}</span></td>"
        f"<td>{confidence_percent:.0f}%</td>"
        "<td><button>Подключиться к диалогу</button></td>"
        "</tr>"
    )


@app.get("/dashboard", response_class=HTMLResponse)
def render_dashboard_html():
    summary = panel.get_dashboard_summary()
    escalations = panel.get_open_escalations()

    escalation_rows = (
        "".join(
            _render_escalation_row(escalation)
            for escalation in escalations
        )
        if escalations
        else "<tr><td colspan='6'>Нет активных эскалаций</td></tr>"
    )

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Панель Администратора и Операторов 1С Техподдержки</title>
        <style>
            body {{ font-family: system-ui, sans-serif; margin: 20px; background: #f4f6f9; color: #333; }}
            h1 {{ color: #1a365d; }}
            .grid {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px; flex: 1; }}
            .card .val {{ font-size: 28px; font-weight: bold; color: #2b6cb0; margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background: #2b6cb0; color: white; }}
            .badge {{ background: #e53e3e; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <h1>Панель Оператора и Супервайзера 1С:Предприятие</h1>

        <div class="grid">
            <div class="card">
                <div>Всего обращений</div>
                <div class="val">{summary.get('total_requests', 0)}</div>
            </div>
            <div class="card">
                <div>Успешные сессии (Success Rate)</div>
                <div class="val">{summary.get('success_rate_percent', 0)}%</div>
            </div>
            <div class="card">
                <div>Удовлетворенность (CSAT 0-10)</div>
                <div class="val">{summary.get('avg_rating_0_10', 0)} / 10</div>
            </div>
            <div class="card">
                <div>Эскалировано на оператора</div>
                <div class="val">{summary.get('escalated_requests', 0)}</div>
            </div>
            <div class="card">
                <div>Среднее время ответа</div>
                <div class="val">{summary.get('avg_response_time_ms', 0)} ms</div>
            </div>
        </div>

        <h2>Открытые Эскалации (Требуют оператора)</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Пользователь</th>
                    <th>Вопрос</th>
                    <th>Причина эскалации</th>
                    <th>Уверенность AI</th>
                    <th>Действие</th>
                </tr>
            </thead>
            <tbody>
                {escalation_rows}
            </tbody>
        </table>
    </body>
    </html>
    """
