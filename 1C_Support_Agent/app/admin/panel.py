from typing import Any, Optional
from support_agent_db.database import Database


class AdminPanel:
    """
    Класс админ-панели для супервайзеров и операторов техподдержки 1С.

    Отвечает за:
    - расчет показателей удовлетворенности CSAT (шкала 0..10);
    - статистику удачных/неудачных/эскалированных сессий;
    - сводную аналитику из SQL-представлений (v_dashboard_summary, v_daily_stats, v_category_stats);
    - мониторинг эскалированных запросов для оперативного подключения оператора.
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.db.initialize()

    def get_user_satisfaction(self) -> dict[str, Any]:
        """
        Возвращает метрики удовлетворенности пользователей (CSAT от 0 до 10).
        """
        row = self.db.fetch_one(
            """
            SELECT
                COUNT(*) as total_feedbacks,
                ROUND(AVG(rating), 2) as avg_rating,
                SUM(CASE WHEN rating >= 8 THEN 1 ELSE 0 END) as positive_feedbacks,
                SUM(CASE WHEN rating <= 4 THEN 1 ELSE 0 END) as negative_feedbacks
            FROM feedback
            """
        ) or {}

        total = row.get("total_feedbacks", 0) or 0
        avg_rating = row.get("avg_rating") or 0.0
        csat_percent = round((row.get("positive_feedbacks", 0) / total * 100), 2) if total > 0 else 0.0

        return {
            "total_feedbacks": total,
            "avg_rating_0_10": avg_rating,
            "csat_percent": csat_percent,
            "positive_count": row.get("positive_feedbacks", 0),
            "negative_count": row.get("negative_feedbacks", 0),
        }

    def get_session_stats(self) -> dict[str, Any]:
        """
        Возвращает количество удачных, неудачных и эскалированных сессий.
        """
        row = self.db.fetch_one(
            """
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_sessions,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_sessions,
                SUM(CASE WHEN status = 'escalated' OR was_escalated = 1 THEN 1 ELSE 0 END) as escalated_sessions,
                ROUND(AVG(response_time_ms), 2) as avg_response_time_ms
            FROM requests
            """
        ) or {}

        total = row.get("total_requests", 0) or 0
        success = row.get("successful_sessions", 0) or 0
        success_rate = round((success / total * 100), 2) if total > 0 else 0.0

        return {
            "total_requests": total,
            "successful_sessions": success,
            "failed_sessions": row.get("failed_sessions", 0) or 0,
            "escalated_sessions": row.get("escalated_sessions", 0) or 0,
            "success_rate_percent": success_rate,
            "avg_response_time_ms": row.get("avg_response_time_ms", 0.0),
        }

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Сводная аналитика дашборда с удовлетворённостью и сессиями."""
        summary = self.db.dashboard_summary()
        summary.update(self.get_user_satisfaction())
        summary.update({"session_metrics": self.get_session_stats()})
        return summary

    def get_daily_stats(self) -> list[dict[str, Any]]:
        """Статистика обращения по дням."""
        return self.db.daily_stats()

    def get_category_stats(self) -> list[dict[str, Any]]:
        """Статистика по категориям проблем 1С."""
        return self.db.category_stats()

    def get_open_escalations(self) -> list[dict[str, Any]]:
        """Возвращает список открытых эскалаций для подключения оператора."""
        return self.db.fetch_all(
            """
            SELECT e.id as escalation_id, e.request_id, e.reason, e.confidence, e.created_at,
                   r.question, u.name as user_name, u.external_id
            FROM escalations e
            JOIN requests r ON e.request_id = r.id
            JOIN users u ON r.user_id = u.id
            WHERE e.status = 'open'
            ORDER BY e.created_at DESC
            """
        )
