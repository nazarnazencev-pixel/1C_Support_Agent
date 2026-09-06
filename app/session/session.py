import threading
import time

from app.agent.agent import SupportAgent
from app.context.context import ConversationStatus
from support_agent_db.database import Database


TERMINAL_STATUSES = {
    ConversationStatus.SOLVED,
    ConversationStatus.ESCALATED,
    ConversationStatus.CLOSED,
}


class Session:
    """
    Одна независимая сессия пользователя.

    Session объединяет:

    - session_id;
    - собственного SupportAgent;
    - время создания;
    - время последней активности;
    - блокировку для последовательной обработки
      запросов внутри одной сессии.

    Каждый Session имеет полностью независимые:

    - историю сообщений;
    - ConversationContext;
    - базу знаний;
    - файловый контекст;
    - состояние последнего запроса.

    Параллельные запросы разных Session могут выполняться
    одновременно.

    Запросы одной Session выполняются последовательно,
    чтобы несколько потоков не изменяли одновременно
    history/context одного SupportAgent.
    """

    def __init__(
        self,
        session_id: str,
    ):
        if not session_id or not session_id.strip():
            raise ValueError(
                "session_id не может быть пустым"
            )

        self.session_id = session_id.strip()

        # -----------------------------------------------------
        # Каждый диалог получает собственного агента.
        # -----------------------------------------------------

        self.agent = SupportAgent()

        # -----------------------------------------------------
        # База данных
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

        # -----------------------------------------------------
        # Временные метки.
        # -----------------------------------------------------

        now = time.time()

        self.created_at = now
        self.last_activity = now

        # -----------------------------------------------------
        # Lock конкретной сессии.
        #
        # SessionManager._lock защищает только словарь
        # SessionManager.
        #
        # Этот lock защищает внутреннее состояние именно
        # этого SupportAgent.
        # -----------------------------------------------------

        self._lock = threading.RLock()

    # =========================================================
    # Активность
    # =========================================================

    def touch(self) -> None:
        """
        Обновляет время последней активности сессии.
        """

        with self._lock:
            self.last_activity = time.time()

    def idle_seconds(self) -> float:
        """
        Возвращает количество секунд бездействия сессии.
        """

        with self._lock:
            return max(
                0.0,
                time.time() - self.last_activity,
            )

    # =========================================================
    # Состояние
    # =========================================================

    @property
    def status(self) -> ConversationStatus:
        """
        Возвращает текущий статус обращения.
        """

        with self._lock:
            return self.agent.context.status

    def is_terminal(self) -> bool:
        """
        Проверяет, является ли обращение завершённым.

        Завершённые состояния:

        - SOLVED
        - ESCALATED
        - CLOSED
        """

        with self._lock:
            return self.status in TERMINAL_STATUSES

    # =========================================================
    # TTL
    # =========================================================

    def is_expired(
        self,
        ttl_seconds: float,
        terminal_grace_seconds: float,
    ) -> bool:
        """
        Проверяет, нужно ли удалить сессию.

        Для обычной сессии используется ttl_seconds.

        Для завершённой сессии используется
        terminal_grace_seconds.
        """

        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds должен быть больше 0"
            )

        if terminal_grace_seconds <= 0:
            raise ValueError(
                "terminal_grace_seconds должен быть больше 0"
            )

        with self._lock:

            idle = self.idle_seconds()

            if self.is_terminal():
                return (
                    idle >= terminal_grace_seconds
                )

            return (
                idle >= ttl_seconds
            )

    # =========================================================
    # Приветствие
    # =========================================================

    def get_greeting(self) -> str:
        """
        Возвращает приветствие агента сессии.
        """
        with self._lock:
            self.touch()
            return self.agent.get_greeting()

    # =========================================================
    # Запрос
    # =========================================================

    def ask(
        self,
        user_message: str,
    ) -> str:
        """
        Передаёт сообщение своему SupportAgent.

        Внутри одной Session запросы выполняются
        последовательно.

        Это предотвращает ситуацию:

            Thread A -> history.append(...)
            Thread B -> history.append(...)
            Thread A -> GigaChat
            Thread B -> GigaChat

        когда сообщения разных запросов могут перемешаться
        в history.

        Даже если GigaChat временно недоступен,
        Session продолжает существовать.
        """

        if (
            not user_message
            or not user_message.strip()
        ):
            raise ValueError(
                "user_message не может быть пустым"
            )

        with self._lock:

            self.touch()

            start_time = time.time()
            req_id = None
            if self.db and self.user_id:
                try:
                    req_id = self.db.create_request(
                        user_id=self.user_id,
                        question=user_message,
                        channel="cli",
                    )
                except Exception:
                    req_id = None

            try:

                answer = self.agent.ask(
                    user_message
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if self.db and req_id:
                    try:
                        was_escalated = (self.agent.context.status == ConversationStatus.ESCALATED)
                        self.db.complete_request(
                            request_id=req_id,
                            answer=answer,
                            status="escalated" if was_escalated else "success",
                            confidence=self.agent.context.hypothesis_confidence,
                            response_time_ms=response_time_ms,
                            was_escalated=was_escalated,
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

                # -------------------------------------------------
                # Обновляем активность после завершения обработки.
                # -------------------------------------------------

                self.touch()

    # =========================================================
    # Вложения
    # =========================================================

    def analyze_file(
        self,
        file_path: str,
        user_message: str,
    ) -> str:
        """
        Анализирует файл через агента текущей сессии.

        Обработка файла также сериализуется относительно
        обычных текстовых запросов этой Session.
        """

        if not file_path:
            raise ValueError(
                "file_path не может быть пустым"
            )

        if (
            not user_message
            or not user_message.strip()
        ):
            raise ValueError(
                "user_message не может быть пустым"
            )

        with self._lock:

            self.touch()

            try:

                return self.agent.analyze_file(
                    file_path=file_path,
                    user_message=user_message,
                )

            finally:

                self.touch()

    # =========================================================
    # Контекст
    # =========================================================

    def get_context(self) -> str:
        """
        Возвращает текущий структурированный контекст.
        """

        with self._lock:
            return self.agent.get_context()

    # =========================================================
    # Состояние последнего запроса
    # =========================================================

    @property
    def last_request_failed(self) -> bool:
        """
        Показывает, завершился ли последний запрос ошибкой.

        True:
            последний запрос завершился ошибкой.

        False:
            последний запрос был успешным.
        """

        with self._lock:
            return self.agent.last_request_failed

    @property
    def last_failed_message(self) -> str | None:
        """
        Возвращает сообщение, которое завершилось ошибкой.

        Если последний запрос был успешным — None.
        """

        with self._lock:
            return self.agent.last_failed_message

    # =========================================================
    # Информация о сессии
    # =========================================================

    def age_seconds(self) -> float:
        """
        Возвращает возраст сессии в секундах.
        """

        with self._lock:
            return max(
                0.0,
                time.time() - self.created_at,
            )

    def is_busy(self) -> bool:
        """
        Показывает, занят ли Session обработкой запроса.

        Используется только для наблюдения/мониторинга.

        ВАЖНО:

        Метод не гарантирует, что состояние не изменится
        сразу после его вызова.
        """

        acquired = self._lock.acquire(
            blocking=False
        )

        if acquired:
            self._lock.release()
            return False

        return True