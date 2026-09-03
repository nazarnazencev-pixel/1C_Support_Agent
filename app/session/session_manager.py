import threading
from typing import Optional

from app.session.session import Session


class SessionManager:
    """
    Менеджер активных пользовательских сессий.

    Архитектура:

        SessionManager
              |
        ┌─────┼─────┐
        ▼     ▼     ▼
    Session A  Session B  Session C
        |         |          |
      Lock A    Lock B     Lock C
        |         |          |
      Agent A   Agent B    Agent C

    SessionManager отвечает за:

    - создание Session;
    - получение Session;
    - удаление Session;
    - TTL;
    - terminal grace period;
    - фоновую очистку;
    - статистику.

    ВАЖНО:

    SessionManager работает только внутри одного
    Python-процесса.

    self._lock защищает только сам словарь сессий
    и состояние менеджера.

    Внутреннее состояние конкретной Session
    защищается собственным Session._lock.

    Поэтому:

        Session A + Session B

    могут обрабатываться параллельно.

    А запросы:

        Session A + Session A

    выполняются последовательно.

    Для нескольких Python-процессов потребуется общее
    хранилище сессий, например Redis или PostgreSQL.
    """

    def __init__(
        self,
        ttl_seconds: float = 30 * 60,
        terminal_grace_seconds: float = 2 * 60,
        cleanup_interval_seconds: float = 5 * 60,
    ):
        # =====================================================
        # Проверка параметров
        # =====================================================

        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds должен быть больше 0"
            )

        if terminal_grace_seconds <= 0:
            raise ValueError(
                "terminal_grace_seconds должен быть больше 0"
            )

        if cleanup_interval_seconds <= 0:
            raise ValueError(
                "cleanup_interval_seconds должен быть больше 0"
            )

        # =====================================================
        # Настройки
        # =====================================================

        self.ttl_seconds = float(
            ttl_seconds
        )

        self.terminal_grace_seconds = float(
            terminal_grace_seconds
        )

        self.cleanup_interval_seconds = float(
            cleanup_interval_seconds
        )

        # =====================================================
        # Хранилище сессий
        # =====================================================

        self._sessions: dict[str, Session] = {}

        # =====================================================
        # Lock менеджера
        #
        # Защищает:
        #
        # - _sessions;
        # - _cleanup_thread;
        # - состояние cleanup.
        #
        # НЕ защищает работу самого Session.
        # =====================================================

        self._lock = threading.RLock()

        # =====================================================
        # Background cleanup
        # =====================================================

        self._cleanup_thread: Optional[
            threading.Thread
        ] = None

        self._stop_event = threading.Event()

        # =====================================================
        # Состояние менеджера
        # =====================================================

        self._shutdown = False

    # =========================================================
    # Нормализация session_id
    # =========================================================

    @staticmethod
    def _normalize_session_id(
        session_id: str,
    ) -> str:
        """
        Проверяет и нормализует session_id.
        """

        if not isinstance(
            session_id,
            str,
        ):
            raise TypeError(
                "session_id должен быть строкой"
            )

        session_id = session_id.strip()

        if not session_id:
            raise ValueError(
                "session_id не может быть пустым"
            )

        return session_id

    # =========================================================
    # Проверка состояния менеджера
    # =========================================================

    def _ensure_running(self) -> None:
        """
        Проверяет, что SessionManager ещё работает.
        """

        if self._shutdown:
            raise RuntimeError(
                "SessionManager уже остановлен"
            )

    # =========================================================
    # Получение / создание
    # =========================================================

    def get_or_create(
        self,
        session_id: str,
    ) -> Session:
        """
        Возвращает существующую Session либо создаёт новую.

        Если существующая Session истекла, она удаляется,
        после чего создаётся новая.

        ВАЖНО:

        Lock удерживается только во время работы
        со словарём _sessions.

        Создание и использование Session не блокирует
        остальные Session.
        """

        session_id = (
            self._normalize_session_id(
                session_id
            )
        )

        with self._lock:

            self._ensure_running()

            session = self._sessions.get(
                session_id
            )

            # -------------------------------------------------
            # Сессия уже существует.
            # -------------------------------------------------

            if session is not None:

                if session.is_expired(
                    ttl_seconds=self.ttl_seconds,
                    terminal_grace_seconds=(
                        self.terminal_grace_seconds
                    ),
                ):

                    del self._sessions[
                        session_id
                    ]

                    session = None

            # -------------------------------------------------
            # Создаём новую Session.
            # -------------------------------------------------

            if session is None:

                session = Session(
                    session_id=session_id
                )

                self._sessions[
                    session_id
                ] = session

            return session

    # =========================================================
    # Получение без создания
    # =========================================================

    def get(
        self,
        session_id: str,
    ) -> Optional[Session]:
        """
        Возвращает существующую Session.

        Если Session отсутствует или истекла,
        возвращает None.

        Новая Session не создаётся.
        """

        if not isinstance(
            session_id,
            str,
        ):
            return None

        session_id = session_id.strip()

        if not session_id:
            return None

        with self._lock:

            if self._shutdown:
                return None

            session = self._sessions.get(
                session_id
            )

            if session is None:
                return None

            # -------------------------------------------------
            # Проверяем TTL.
            # -------------------------------------------------

            if session.is_expired(
                ttl_seconds=self.ttl_seconds,
                terminal_grace_seconds=(
                    self.terminal_grace_seconds
                ),
            ):

                del self._sessions[
                    session_id
                ]

                return None

            return session

    # =========================================================
    # Основной вход
    # =========================================================

    def ask(
        self,
        session_id: str,
        user_message: str,
    ) -> str:
        """
        Основная точка входа.

        Получает Session и передаёт сообщение
        её SupportAgent.

        ВАЖНО:

        SessionManager НЕ держит свой lock во время
        обращения к GigaChat.

        Поэтому запросы разных Session могут выполняться
        параллельно.
        """

        session = self.get_or_create(
            session_id=session_id
        )

        return session.ask(
            user_message=user_message
        )

    # =========================================================
    # Работа с файлами
    # =========================================================

    def analyze_file(
        self,
        session_id: str,
        file_path: str,
        user_message: str,
    ) -> str:
        """
        Анализирует файл в рамках конкретной Session.
        """

        session = self.get_or_create(
            session_id=session_id
        )

        return session.analyze_file(
            file_path=file_path,
            user_message=user_message,
        )

    # =========================================================
    # Удаление
    # =========================================================

    def remove(
        self,
        session_id: str,
    ) -> bool:
        """
        Принудительно удаляет Session.

        Возвращает:

            True
                Session существовала и была удалена.

            False
                Session не существовала.

        ВАЖНО:

        Если другой поток уже получил ссылку на Session
        и обрабатывает запрос, удаление из менеджера
        не уничтожает сам объект Session мгновенно.

        Уже выполняющийся запрос сможет завершиться.

        После удаления следующий get_or_create()
        создаст новую Session с тем же session_id.
        """

        if not isinstance(
            session_id,
            str,
        ):
            return False

        session_id = session_id.strip()

        if not session_id:
            return False

        with self._lock:

            return (
                self._sessions.pop(
                    session_id,
                    None,
                )
                is not None
            )

    # =========================================================
    # Очистка
    # =========================================================

    def cleanup_once(self) -> list[str]:
        """
        Выполняет один проход очистки.

        Удаляет:

        - обычные Session после TTL;
        - терминальные Session после grace period.

        Возвращает список удалённых session_id.
        """

        removed: list[str] = []

        with self._lock:

            if self._shutdown:
                return removed

            # -------------------------------------------------
            # Создаём snapshot.
            #
            # Это позволяет безопасно удалять элементы
            # из _sessions во время обхода.
            # -------------------------------------------------

            sessions = list(
                self._sessions.items()
            )

            for (
                session_id,
                session,
            ) in sessions:

                if session.is_expired(
                    ttl_seconds=self.ttl_seconds,
                    terminal_grace_seconds=(
                        self.terminal_grace_seconds
                    ),
                ):

                    # -------------------------------------------------
                    # Важно:
                    #
                    # Не удаляем новую Session, если за время
                    # проверки словарь уже был изменён.
                    # -------------------------------------------------

                    current_session = (
                        self._sessions.get(
                            session_id
                        )
                    )

                    if current_session is not session:
                        continue

                    del self._sessions[
                        session_id
                    ]

                    removed.append(
                        session_id
                    )

        return removed

    # =========================================================
    # Background cleanup
    # =========================================================

    def start_background_cleanup(
        self,
    ) -> None:
        """
        Запускает фоновый поток очистки.

        Повторный вызов безопасен.

        Если cleanup уже работает, новый поток
        не создаётся.
        """

        with self._lock:

            self._ensure_running()

            if (
                self._cleanup_thread is not None
                and self._cleanup_thread.is_alive()
            ):
                return

            self._stop_event.clear()

            self._cleanup_thread = (
                threading.Thread(
                    target=self._cleanup_loop,
                    name="session-cleanup",
                    daemon=True,
                )
            )

            self._cleanup_thread.start()

    # =========================================================
    # Cleanup loop
    # =========================================================

    def _cleanup_loop(self) -> None:
        """
        Внутренний цикл фоновой очистки.
        """

        while not self._stop_event.wait(
            self.cleanup_interval_seconds
        ):

            try:

                self.cleanup_once()

            except Exception:
                # -------------------------------------------------
                # Cleanup не должен умереть из-за одной
                # неожиданной ошибки.
                #
                # Здесь намеренно не используем logger,
                # чтобы не добавлять лишнюю зависимость.
                # При желании ниже можно подключить logging.
                # -------------------------------------------------

                continue

    # =========================================================
    # Остановка background cleanup
    # =========================================================

    def stop_background_cleanup(
        self,
    ) -> None:
        """
        Останавливает фоновую очистку.

        Безопасен при повторном вызове.
        """

        with self._lock:

            thread = self._cleanup_thread

            if thread is None:
                return

            # -------------------------------------------------
            # Если метод вызван самим cleanup-потоком,
            # нельзя делать thread.join() на самого себя.
            # -------------------------------------------------

            if thread is threading.current_thread():

                self._stop_event.set()

                self._cleanup_thread = None

                return

            self._stop_event.set()

        # -----------------------------------------------------
        # join выполняем ВНЕ self._lock.
        # -----------------------------------------------------

        thread.join()

        with self._lock:

            if self._cleanup_thread is thread:

                self._cleanup_thread = None

    # =========================================================
    # Полное завершение менеджера
    # =========================================================

    def shutdown(self) -> None:
        """
        Полностью останавливает SessionManager.

        После shutdown:

        - новые Session создавать нельзя;
        - get_or_create() выбрасывает RuntimeError;
        - background cleanup останавливается.

        Уже существующие Session сами по себе не используются
        менеджером после shutdown.
        """

        with self._lock:

            if self._shutdown:
                return

            self._shutdown = True

            thread = self._cleanup_thread

            self._stop_event.set()

        # -----------------------------------------------------
        # Останавливаем cleanup вне lock.
        # -----------------------------------------------------

        if (
            thread is not None
            and thread is not threading.current_thread()
        ):

            thread.join()

        with self._lock:

            if self._cleanup_thread is thread:

                self._cleanup_thread = None

    # =========================================================
    # Статистика
    # =========================================================

    def active_count(self) -> int:
        """
        Возвращает количество Session,
        зарегистрированных в менеджере.

        Истёкшие Session удаляются при обычном
        обращении или cleanup.
        """

        with self._lock:
            return len(
                self._sessions
            )

    # =========================================================
    # Session IDs
    # =========================================================

    def session_ids(self) -> list[str]:
        """
        Возвращает список активных session_id.
        """

        with self._lock:

            return list(
                self._sessions.keys()
            )

    # =========================================================
    # Проверка существования
    # =========================================================

    def exists(
        self,
        session_id: str,
    ) -> bool:
        """
        Проверяет существование активной Session.

        Истёкшая Session автоматически считается
        несуществующей.
        """

        return (
            self.get(session_id)
            is not None
        )

    # =========================================================
    # Получение количества завершённых обращений
    # =========================================================

    def terminal_count(self) -> int:
        """
        Возвращает количество Session,
        находящихся в терминальном состоянии:

        - SOLVED
        - ESCALATED
        - CLOSED
        """

        with self._lock:

            count = 0

            for session in self._sessions.values():

                if session.is_terminal():
                    count += 1

            return count

    # =========================================================
    # Очистка всех сессий
    # =========================================================

    def clear(self) -> int:
        """
        Принудительно удаляет все Session.

        Возвращает количество удалённых Session.

        Используется преимущественно:

        - при завершении приложения;
        - в тестах;
        - при административной очистке.
        """

        with self._lock:

            count = len(
                self._sessions
            )

            self._sessions.clear()

            return count