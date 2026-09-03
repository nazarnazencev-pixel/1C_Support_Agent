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
