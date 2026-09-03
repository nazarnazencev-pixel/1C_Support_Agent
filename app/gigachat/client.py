import logging
from typing import Any

import httpx
import truststore

truststore.inject_into_ssl()

from gigachat import GigaChat
from gigachat.exceptions import (
    GigaChatException,
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    ServerError,
)

from app.config.settings import (
    GIGACHAT_BASE_URL,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_SCOPE,
)

from app.gigachat.errors import (
    GigaChatAuthenticationError,
    GigaChatBadRequestError,
    GigaChatFatalError,
    GigaChatNetworkError,
    GigaChatRateLimitError,
    GigaChatServerError,
    GigaChatTimeoutError,
)


logger = logging.getLogger(__name__)


class GigaChatClient:
    """
    Единая обёртка над GigaChat.

    Ответственность класса:

    - создание GigaChat клиента;
    - timeout;
    - встроенный retry SDK;
    - обработка временных HTTP-ошибок;
    - обработка timeout;
    - обработка сетевых ошибок;
    - нормализация исключений;
    - логирование.

    SupportAgent не должен знать внутренние типы
    исключений GigaChat SDK.
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
    ):
        if timeout <= 0:
            raise ValueError(
                "timeout должен быть больше 0"
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries не может быть отрицательным"
            )

        if retry_backoff_factor < 0:
            raise ValueError(
                "retry_backoff_factor не может быть отрицательным"
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = (
            retry_backoff_factor
        )

        self.client = GigaChat(
            base_url=GIGACHAT_BASE_URL,
            credentials=GIGACHAT_CREDENTIALS,
            scope=GIGACHAT_SCOPE,

            # -------------------------------------------------
            # Максимальное время одного HTTP-запроса.
            # -------------------------------------------------

            timeout=timeout,

            # -------------------------------------------------
            # Встроенный retry GigaChat SDK.
            #
            # max_retries=3 означает до трёх повторов
            # после первоначальной попытки.
            # -------------------------------------------------

            max_retries=max_retries,

            retry_backoff_factor=(
                retry_backoff_factor
            ),

            # -------------------------------------------------
            # HTTP-коды, для которых имеет смысл повторить
            # запрос.
            # -------------------------------------------------

            retry_on_status_codes=(
                429,
                500,
                502,
                503,
                504,
            ),
        )

    # =========================================================
    # Основной запрос
    # =========================================================

    def chat(
        self,
        request: Any,
    ) -> Any:
        """
        Выполняет chat-запрос к GigaChat.

        Retry временных HTTP-ошибок выполняется
        встроенным механизмом GigaChat SDK.

        После исчерпания retry исключение
        нормализуется в наше исключение.
        """

        try:

            return self.client.chat(request)

        # -----------------------------------------------------
        # Timeout httpx
        # -----------------------------------------------------
        #
        # Важно:
        # GigaChat использует httpx, поэтому обрабатываем
        # именно httpx.TimeoutException.
        #
        # Это отдельный класс от обычного Python TimeoutError.
        # -----------------------------------------------------

        except httpx.TimeoutException as exc:

            logger.warning(
                "GigaChat timeout after %.1f seconds",
                self.timeout,
            )

            raise GigaChatTimeoutError(
                "GigaChat не ответил вовремя."
            ) from exc

        # -----------------------------------------------------
        # Сетевые ошибки httpx
        # -----------------------------------------------------

        except httpx.NetworkError as exc:

            logger.warning(
                "GigaChat network error: %s",
                exc,
            )

            raise GigaChatNetworkError(
                "Не удалось установить соединение с GigaChat."
            ) from exc

        # -----------------------------------------------------
        # Авторизация
        # -----------------------------------------------------

        except AuthenticationError as exc:

            logger.error(
                "GigaChat authentication error: %s",
                exc,
            )

            raise GigaChatAuthenticationError(
                "Не удалось авторизоваться в GigaChat."
            ) from exc

        # -----------------------------------------------------
        # Rate limit
        # -----------------------------------------------------

        except RateLimitError as exc:

            logger.warning(
                "GigaChat rate limit after retries: %s",
                exc,
            )

            raise GigaChatRateLimitError(
                "GigaChat временно ограничил количество запросов."
            ) from exc

        # -----------------------------------------------------
        # Server error
        # -----------------------------------------------------

        except ServerError as exc:

            logger.warning(
                "GigaChat server error after retries: %s",
                exc,
            )

            raise GigaChatServerError(
                "GigaChat временно недоступен."
            ) from exc

        # -----------------------------------------------------
        # Bad request
        # -----------------------------------------------------

        except BadRequestError as exc:

            logger.error(
                "GigaChat bad request: %s",
                exc,
            )

            raise GigaChatBadRequestError(
                "GigaChat отклонил запрос."
            ) from exc

        # -----------------------------------------------------
        # Python timeout.
        #
        # Оставляем эту обработку дополнительно:
        # некоторые исключения могут приходить как обычный
        # TimeoutError.
        # -----------------------------------------------------

        except TimeoutError as exc:

            logger.warning(
                "GigaChat timeout after %.1f seconds",
                self.timeout,
            )

            raise GigaChatTimeoutError(
                "GigaChat не ответил вовремя."
            ) from exc

        # -----------------------------------------------------
        # Python ConnectionError
        # -----------------------------------------------------

        except ConnectionError as exc:

            logger.warning(
                "GigaChat connection error: %s",
                exc,
            )

            raise GigaChatNetworkError(
                "Не удалось установить соединение с GigaChat."
            ) from exc

        # -----------------------------------------------------
        # Низкоуровневая ошибка ОС.
        # -----------------------------------------------------

        except OSError as exc:

            logger.warning(
                "GigaChat OS/network error: %s",
                exc,
            )

            raise GigaChatNetworkError(
                "Произошла сетевая ошибка при обращении к GigaChat."
            ) from exc

        # -----------------------------------------------------
        # Остальные ошибки GigaChat SDK
        # -----------------------------------------------------

        except GigaChatException as exc:

            logger.exception(
                "Unhandled GigaChat SDK error"
            )

            raise GigaChatFatalError(
                "Произошла ошибка при обращении к GigaChat."
            ) from exc

        # -----------------------------------------------------
        # Совсем неизвестная ошибка.
        # -----------------------------------------------------

        except Exception as exc:

            logger.exception(
                "Unexpected GigaChat error"
            )

            raise GigaChatFatalError(
                "Произошла неожиданная ошибка при обращении к GigaChat."
            ) from exc

    # =========================================================
    # Работа с файлами
    # =========================================================

    def upload(
        self,
        *args,
        **kwargs,
    ) -> Any:
        """
        Загружает файл через GigaChat.

        Сетевые ошибки и timeout нормализуются.
        """

        try:

            return self.client.upload(
                *args,
                **kwargs,
            )

        except httpx.TimeoutException as exc:

            logger.warning(
                "GigaChat file upload timeout after %.1f seconds",
                self.timeout,
            )

            raise GigaChatTimeoutError(
                "GigaChat не успел загрузить файл."
            ) from exc

        except httpx.NetworkError as exc:

            logger.warning(
                "GigaChat file upload network error: %s",
                exc,
            )

            raise GigaChatNetworkError(
                "Не удалось загрузить файл в GigaChat."
            ) from exc

        except TimeoutError as exc:

            logger.warning(
                "GigaChat file upload timeout"
            )

            raise GigaChatTimeoutError(
                "GigaChat не успел загрузить файл."
            ) from exc

        except ConnectionError as exc:

            logger.warning(
                "GigaChat file upload connection error"
            )

            raise GigaChatNetworkError(
                "Не удалось загрузить файл в GigaChat."
            ) from exc

        except OSError as exc:

            logger.warning(
                "GigaChat file upload OS error"
            )

            raise GigaChatNetworkError(
                "Произошла сетевая ошибка при загрузке файла."
            ) from exc

        except AuthenticationError as exc:

            logger.error(
                "GigaChat authentication error during upload"
            )

            raise GigaChatAuthenticationError(
                "Не удалось авторизоваться в GigaChat."
            ) from exc

        except GigaChatException as exc:

            logger.exception(
                "GigaChat file upload error"
            )

            raise GigaChatFatalError(
                "Не удалось загрузить файл в GigaChat."
            ) from exc

        except Exception as exc:

            logger.exception(
                "Unexpected GigaChat file upload error"
            )

            raise GigaChatFatalError(
                "Произошла ошибка при загрузке файла."
            ) from exc

    # =========================================================
    # Делегирование остальных методов
    # =========================================================

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        """
        Передаёт остальные методы непосредственно
        внутреннему GigaChat клиенту.

        chat() и upload() намеренно перехватываются
        выше и проходят через нашу обработку ошибок.
        """

        return getattr(
            self.client,
            name,
        )