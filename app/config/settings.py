import os

from dotenv import load_dotenv

load_dotenv()

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")
GIGACHAT_SCOPE = os.getenv(
    "GIGACHAT_SCOPE",
    "GIGACHAT_API_PERS",
)
GIGACHAT_MODEL = os.getenv(
    "GIGACHAT_MODEL",
    "GigaChat-3-Ultra",
)

GIGACHAT_BASE_URL = "https://api.giga.chat/v1"


def validate_config() -> None:
    """
    Проверяет обязательные настройки при старте приложения.

    Раньше GIGACHAT_CREDENTIALS по умолчанию был пустой строкой
    без какой-либо проверки: при отсутствии .env приложение
    запускалось нормально, а ошибка авторизации всплывала только
    при первом реальном обращении к GigaChat, в виде малопонятной
    ошибки сервиса - вместо явной и понятной ошибки конфигурации
    сразу при старте.

    Вызывается из точек входа (main.py, app/api/chat_server.py),
    а не из конструкторов SupportAgent/GigaChatClient - иначе
    юнит-тесты, которые создают эти объекты напрямую без реальных
    credentials (и не делают реальных сетевых вызовов), перестали
    бы работать.
    """

    if not GIGACHAT_CREDENTIALS:
        raise RuntimeError(
            "Не задана переменная окружения GIGACHAT_CREDENTIALS. "
            "Укажите её в .env (см. .env.example) перед запуском."
        )


# Жёсткий бюджет ответа веб-чата: один сетевой вызов GigaChat короче 5 секунд.
GIGACHAT_TIMEOUT_SECONDS = float(os.getenv("GIGACHAT_TIMEOUT_SECONDS", "3.8"))
WEB_RESPONSE_BUDGET_MS = 5000
