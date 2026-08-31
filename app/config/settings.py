import os

from dotenv import load_dotenv

load_dotenv()

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
GIGACHAT_SCOPE = os.getenv(
    "GIGACHAT_SCOPE",
    "GIGACHAT_API_PERS",
)
GIGACHAT_MODEL = os.getenv(
    "GIGACHAT_MODEL",
    "GigaChat-3-Ultra",
)

GIGACHAT_BASE_URL = "https://api.giga.chat/v1"

if not GIGACHAT_CREDENTIALS:
    raise ValueError(
        "Не найден GIGACHAT_CREDENTIALS в файле .env"
    )