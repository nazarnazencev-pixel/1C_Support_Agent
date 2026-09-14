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


def parse_request_timeout(value: str) -> float:
    try:
        timeout_seconds = float(value)
    except ValueError as failure:
        raise RuntimeError("GIGACHAT_REQUEST_TIMEOUT должен быть числом от 1 до 60 секунд.") from failure
    if not 1 <= timeout_seconds <= 60:
        raise RuntimeError("GIGACHAT_REQUEST_TIMEOUT должен быть числом от 1 до 60 секунд.")
    return timeout_seconds


GIGACHAT_REQUEST_TIMEOUT = parse_request_timeout(os.getenv("GIGACHAT_REQUEST_TIMEOUT", "30"))

# -----------------------------------------------------------------
# База знаний
# -----------------------------------------------------------------

# "vector" - семантический поиск по эмбеддингам (см.
#            app/knowledge/vector_store.py), с автоматическим
#            откатом на поиск по ключевым словам, если индекс или
#            Embeddings API недоступны.
# "keyword" - только поиск по ключевым словам (LocalKnowledgeBase),
#            без обращения к Embeddings API вообще.
KNOWLEDGE_BACKEND = os.getenv("KNOWLEDGE_BACKEND", "vector")

KNOWLEDGE_PATH = os.getenv("KNOWLEDGE_PATH", "data/knowledge")

KNOWLEDGE_INDEX_PATH = os.getenv(
    "KNOWLEDGE_INDEX_PATH",
    "data/knowledge/index",
)

GIGACHAT_EMBEDDING_MODEL = os.getenv(
    "GIGACHAT_EMBEDDING_MODEL",
    "Embeddings",
)

KNOWLEDGE_EMBEDDING_TIMEOUT = float(
    os.getenv("KNOWLEDGE_EMBEDDING_TIMEOUT", "1.5")
)

# Минимальное косинусное сходство, ниже которого найденный фрагмент
# считается нерелевантным и отбрасывается (после чего, если совсем
# ничего не осталось, включается откат на поиск по ключевым словам).
KNOWLEDGE_MIN_SCORE = float(
    os.getenv("KNOWLEDGE_MIN_SCORE", "0.15")
)


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
