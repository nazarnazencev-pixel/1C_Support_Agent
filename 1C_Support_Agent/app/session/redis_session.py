import json
import logging
from typing import Optional, Any
from gigachat.models import Messages, MessagesRole
from app.session.session import Session
from app.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


class RedisSessionManager(SessionManager):
    """
    Распределённый менеджер сессий на базе Redis с автоматическим фолбэком в память.

    Позволяет хранить метаданные сессий, историю и состояния в Redis для
    горизонтального масштабирования на несколько серверов.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        ttl_seconds: float = 30 * 60,
        terminal_grace_seconds: float = 2 * 60,
        cleanup_interval_seconds: float = 5 * 60,
    ):
        super().__init__(
            ttl_seconds=ttl_seconds,
            terminal_grace_seconds=terminal_grace_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
        )

        self.redis_client = None
        try:
            import redis
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_timeout=2.0,
            )
            self.redis_client.ping()
            logger.info("Успешное подключение к Redis: %s:%d", redis_host, redis_port)
        except Exception as exc:
            logger.warning("Redis недоступен (%s). Используется локальное хранилище сессий.", exc)
            self.redis_client = None

    def save_session_state(self, session: Session) -> bool:
        """Сохраняет состояние, контекст и историю сообщений сессии в Redis."""
        if not self.redis_client:
            return False

        try:
            history_data = [
                {
                    "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                    "content": msg.content,
                }
                for msg in session.agent.history
            ]

            state = {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "status": session.status.value,
                "user_id": session.user_id,
                "context": session.agent.context.to_dict(),
                "history": history_data,
            }
            key = f"session:{session.session_id}"
            self.redis_client.setex(key, int(self.ttl_seconds), json.dumps(state, ensure_ascii=False))
            return True
        except Exception as exc:
            logger.error("Ошибка сохранения сессии в Redis: %s", exc)
            return False

    def load_session_state(self, session_id: str) -> Optional[dict[str, Any]]:
        """Загружает метаданные и историю сессии из Redis."""
        if not self.redis_client:
            return None

        try:
            key = f"session:{session_id}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as exc:
            logger.error("Ошибка чтения сессии из Redis: %s", exc)
        return None

    def _hydrate_session_from_redis(self, session_id: str) -> Optional[Session]:
        """Создает сессию и гидрирует её из Redis при наличии сохранённого состояния."""
        data = self.load_session_state(session_id)
        if not data:
            return None

        session = Session(session_id=session_id)
        session.created_at = data.get("created_at", session.created_at)
        session.last_activity = data.get("last_activity", session.last_activity)

        # Восстановление истории
        history_raw = data.get("history", [])
        if history_raw:
            session.agent.history = [
                Messages(
                    role=MessagesRole(item["role"]),
                    content=item["content"],
                )
                for item in history_raw
            ]

        # Восстановление контекста.
        #
        # Раньше здесь вручную копировались 4 поля из ~20 (и не
        # восстанавливался status) - через restore_from_dict()
        # восстанавливается всё, что было сохранено в to_dict().
        context_raw = data.get("context", {})
        if context_raw:
            session.agent.context.restore_from_dict(
                context_raw
            )

        return session

    def get_or_create(self, session_id: str) -> Session:
        """Возвращает локальную сессию или восстанавливает из Redis, иначе создаёт новую."""
        session_id = self._normalize_session_id(session_id)

        with self._lock:
            self._ensure_running()
            session = self._sessions.get(session_id)

            if session is not None and session.is_expired(
                ttl_seconds=self.ttl_seconds,
                terminal_grace_seconds=self.terminal_grace_seconds,
            ):
                del self._sessions[session_id]
                session = None

            if session is None:
                session = self._hydrate_session_from_redis(session_id)
                if session is None:
                    session = Session(session_id=session_id)
                self._sessions[session_id] = session

            return session

    def ask(self, session_id: str, user_message: str) -> str:
        """Обрабатывает сообщение и синхронизирует состояние в Redis."""
        session = self.get_or_create(session_id)
        answer = session.ask(user_message)
        self.save_session_state(session)
        return answer
