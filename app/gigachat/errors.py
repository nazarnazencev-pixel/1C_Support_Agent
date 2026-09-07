class GigaChatClientError(Exception):
    """
    Базовая ошибка взаимодействия с GigaChat.
    """


class GigaChatTemporaryError(GigaChatClientError):
    """
    Временная ошибка.

    Повтор запроса потенциально может помочь.
    """


class GigaChatTimeoutError(GigaChatTemporaryError):
    """
    GigaChat не ответил за установленный timeout.
    """


class GigaChatNetworkError(GigaChatTemporaryError):
    """
    Ошибка сетевого соединения с GigaChat.
    """


class GigaChatRateLimitError(GigaChatTemporaryError):
    """
    GigaChat вернул ошибку ограничения частоты запросов.
    """


class GigaChatServerError(GigaChatTemporaryError):
    """
    GigaChat вернул серверную ошибку 5xx.
    """


class GigaChatAuthenticationError(GigaChatClientError):
    """
    Ошибка авторизации.
    """


class GigaChatBadRequestError(GigaChatClientError):
    """
    Некорректный запрос.
    """


class GigaChatFatalError(GigaChatClientError):
    """
    Ошибка, которую повторять бессмысленно.
    """


def to_user_message(error: BaseException) -> str:
    """
    Преобразует ЛЮБУЮ ошибку в безопасное сообщение для
    пользователя.

    Технические детали (traceback, credentials, внутренние
    исключения SDK/БД) наружу никогда не показываются - вызывающий
    код (main.py, app/api/chat_server.py, SupportAgent) должен
    использовать эту функцию вместо str(error) в любом месте,
    где ошибка может попасть в ответ пользователю.
    """

    if isinstance(error, GigaChatTimeoutError):
        return (
            "Сервис обработки обращений не успел "
            "ответить. Пожалуйста, повторите запрос."
        )

    if isinstance(error, GigaChatNetworkError):
        return (
            "Сейчас не удаётся связаться с сервисом "
            "обработки обращений. Пожалуйста, повторите запрос."
        )

    if isinstance(error, GigaChatRateLimitError):
        return (
            "Сервис обработки обращений временно перегружен. "
            "Пожалуйста, повторите запрос немного позже."
        )

    if isinstance(error, GigaChatServerError):
        return (
            "Сервис обработки обращений временно недоступен. "
            "Пожалуйста, повторите запрос немного позже."
        )

    if isinstance(error, GigaChatAuthenticationError):
        return (
            "Сервис обработки обращений временно недоступен. "
            "Обратитесь к администратору системы."
        )

    if isinstance(error, GigaChatBadRequestError):
        return (
            "Не удалось обработать запрос. "
            "Попробуйте сформулировать сообщение иначе."
        )

    if isinstance(error, GigaChatClientError):
        # Покрывает GigaChatFatalError и любые другие подклассы,
        # для которых нет более специфичного сообщения выше.
        return (
            "Не удалось получить ответ от сервиса "
            "обработки обращений. Пожалуйста, повторите запрос."
        )

    # Полностью непредвиденная ошибка (БД, баг, что угодно ещё) -
    # текст исключения пользователю всё равно не показываем.
    return (
        "Произошла непредвиденная ошибка при обработке "
        "запроса. Пожалуйста, повторите запрос или "
        "обратитесь к администратору системы."
    )
