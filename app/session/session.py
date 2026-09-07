import logging
import threading
import time

from app.agent.agent import SupportAgent
from app.context.context import ConversationStatus
from support_agent_db.database import Database


logger = logging.getLogger(__name__)


TERMINAL_STATUSES = {
    ConversationStatus.SOLVED,
    ConversationStatus.ESCALATED,
    ConversationStatus.CLOSED,
}

OPERATOR_CONNECTING_MESSAGE = "СОЕДИНЕНИЕ С ОПЕРАТОРОМ В ДАННЫЙ МОМЕНТ В РАЗРАБОТКЕ"

# Значения по умолчанию - используются, если БД недоступна или
# строка agent_settings отсутствует/повреждена. В остальных случаях
# читаем актуальное значение из agent_settings (см. schema.sql).
DEFAULT_CONFIDENCE_THRESHOLD = 0.80
DEFAULT_MAX_KNOWLEDGE_RESULTS = 3
DEFAULT_TARGET_RESPONSE_TIME_MS = 5000


def _read_float_setting(
    db: Database | None,
    key: str,
    default: float,
) -> float:
    if not db:
        return default

    try:
        value = db.get_setting(key)
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        logger.warning(
            "Некорректное значение настройки %s в agent_settings, "
            "используется значение по умолчанию",
            key,
        )
        return default


def _read_int_setting(
    db: Database | None,
    key: str,
    default: int,
) -> int:
    if not db:
        return default

    try:
        value = db.get_setting(key)
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        logger.warning(
            "Некорректное значение настройки %s в agent_settings, "
            "используется значение по умолчанию",
            key,
        )
        return default


class Session:
    """
    Одна независимая сессия пользователя.
    """

    def __init__(
        self,
        session_id: str,
        confidence_threshold: float | None = None,
    ):
        if not session_id or not session_id.strip():
            raise ValueError(
                "session_id не может быть пустым"
            )

        self.session_id = session_id.strip()

        # -----------------------------------------------------
        # БД поднимаем ДО агента - agent_settings оттуда влияют
        # на то, с какими параметрами создаётся SupportAgent.
        # -----------------------------------------------------

        try:
            self.db = Database()
            self.db.initialize()
            existing_user = self.db.fetch_one("SELECT id FROM users WHERE external_id = ?", (self.session_id,))
            if existing_user:
                self.user_id = existing_user["id"]
            else:
                self.user_id = self.db.create_user(name=f"User_{self.session_id}", external_id=self.session_id)
        except Exception:
            self.db = None
            self.user_id = None

        # confidence_threshold, если передан явно (например, в
        # тестах) - имеет приоритет над agent_settings.
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else _read_float_setting(
                self.db,
                "confidence_threshold",
                DEFAULT_CONFIDENCE_THRESHOLD,
            )
        )

        self.target_response_time_ms = _read_int_setting(
            self.db,
            "target_response_time_ms",
            DEFAULT_TARGET_RESPONSE_TIME_MS,
        )

        max_knowledge_results = _read_int_setting(
            self.db,
            "max_knowledge_results",
            DEFAULT_MAX_KNOWLEDGE_RESULTS,
        )

        self.agent = SupportAgent(
            max_knowledge_results=max_knowledge_results
        )
        self.last_request_id: int | None = None

        now = time.time()
        self.created_at = now
        self.last_activity = now
        self._lock = threading.RLock()

    def touch(self) -> None:
        with self._lock:
            self.last_activity = time.time()

    def idle_seconds(self) -> float:
        with self._lock:
            return max(
                0.0,
                time.time() - self.last_activity,
            )

    @property
    def status(self) -> ConversationStatus:
        with self._lock:
            return self.agent.context.status

    def is_terminal(self) -> bool:
        with self._lock:
            return self.status in TERMINAL_STATUSES

    def is_expired(
        self,
        ttl_seconds: float,
        terminal_grace_seconds: float,
    ) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds должен быть больше 0")
        if terminal_grace_seconds <= 0:
            raise ValueError("terminal_grace_seconds должен быть больше 0")

        with self._lock:
            idle = self.idle_seconds()
            if self.is_terminal():
                return idle >= terminal_grace_seconds
            return idle >= ttl_seconds

    def get_greeting(self) -> str:
        with self._lock:
            self.touch()
            return self.agent.get_greeting()

    def _ensure_user_in_db(self) -> None:
        if not self.db:
            return
        if not self.user_id:
            self.user_id = self.db.create_user(name=f"User_{self.session_id}", external_id=self.session_id)
        else:
            existing = self.db.fetch_one("SELECT id FROM users WHERE id = ?", (self.user_id,))
            if not existing:
                existing_user = self.db.fetch_one("SELECT id FROM users WHERE external_id = ?", (self.session_id,))
                if existing_user:
                    self.user_id = existing_user["id"]
                else:
                    self.user_id = self.db.create_user(name=f"User_{self.session_id}", external_id=self.session_id)

    def ask(
        self,
        user_message: str,
    ) -> str:
        if not user_message or not user_message.strip():
            raise ValueError("user_message не может быть пустым")

        with self._lock:
            self.touch()

            start_time = time.time()
            req_id = None
            if self.db:
                try:
                    self._ensure_user_in_db()
                    req_id = self.db.create_request(
                        user_id=self.user_id,
                        question=user_message,
                        channel="cli",
                        # Категория ещё не известна на момент
                        # создания запроса (её определит агент по
                        # ходу ответа) - но если в контексте с
                        # прошлого шага уже что-то есть, полезно
                        # проставить сразу; complete_request ниже
                        # обновит значение на актуальное.
                        category=self.agent.context.category or None,
                    )
                    self.last_request_id = req_id
                except Exception:
                    req_id = None

            try:
                answer = self.agent.ask(user_message)
                response_time_ms = int((time.time() - start_time) * 1000)

                if response_time_ms > self.target_response_time_ms:
                    logger.warning(
                        "Ответ занял %d мс, что превышает "
                        "целевое время %d мс (agent_settings."
                        "target_response_time_ms)",
                        response_time_ms,
                        self.target_response_time_ms,
                    )

                # -----------------------------------------------------
                # Проверка уверенности агента (< 80% порог)
                # -----------------------------------------------------
                confidence = self.agent.context.hypothesis_confidence
                should_escalate = False

                if (
                    self.agent.context.current_hypothesis
                    and confidence < self.confidence_threshold
                ) or self.agent.context.status == ConversationStatus.ESCALATED:
                    should_escalate = True
                    self.agent.context.escalate("Уверенность ответа ниже допустимого порога")
                    answer = OPERATOR_CONNECTING_MESSAGE

                if self.db and req_id:
                    try:
                        self.db.complete_request(
                            request_id=req_id,
                            answer=answer,
                            status="escalated" if should_escalate else "success",
                            confidence=confidence,
                            response_time_ms=response_time_ms,
                            was_escalated=should_escalate,
                            # Актуальная категория - агент мог
                            # определить/уточнить её именно в этом
                            # ответе (см. раздел 14 системного
                            # промпта / STATE_UPDATE).
                            category=self.agent.context.category or None,
                        )
                        if should_escalate:
                            self.db.add_escalation(
                                request_id=req_id,
                                reason="Низкая уверенность AI ответа (<80%)",
                                confidence=confidence,
                            )
                    except Exception:
                        pass

                return answer

            except Exception as exc:
                response_time_ms = int((time.time() - start_time) * 1000)
                if self.db and req_id:
                    try:
                        self.db.complete_request(
                            request_id=req_id,
                            answer="",
                            status="failed",
                            response_time_ms=response_time_ms,
                            error_message=str(exc),
                        )
                    except Exception:
                        pass
                raise
            finally:
                self.touch()

    def submit_csat_feedback(self, rating: int, comment: str | None = None) -> int | None:
        """
        Сохраняет авто-оценку удовлетворенности пользователя (CSAT) от 0 до 10 в БД.
        """
        if not (0 <= rating <= 10):
            raise ValueError("Рейтинг удовлетворенности должен быть в диапазоне от 0 до 10")

        with self._lock:
            if self.db and self.last_request_id:
                try:
                    return self.db.add_feedback(
                        request_id=self.last_request_id,
                        rating=rating,
                        comment=comment,
                    )
                except Exception:
                    return None
            return None

    def analyze_file(
        self,
        file_path: str,
        user_message: str,
    ) -> str:
        if not file_path:
            raise ValueError("file_path не может быть пустым")
        if not user_message or not user_message.strip():
            raise ValueError("user_message не может быть пустым")

        with self._lock:
            self.touch()
            try:
                return self.agent.analyze_file(
                    file_path=file_path,
                    user_message=user_message,
                )
            finally:
                self.touch()

    def get_context(self) -> str:
        with self._lock:
            return self.agent.get_context()

    @property
    def last_request_failed(self) -> bool:
        with self._lock:
            return self.agent.last_request_failed

    @property
    def last_failed_message(self) -> str | None:
        with self._lock:
            return self.agent.last_failed_message

    def age_seconds(self) -> float:
        with self._lock:
            return max(0.0, time.time() - self.created_at)

    def is_busy(self) -> bool:
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True
