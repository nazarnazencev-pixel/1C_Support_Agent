import truststore

truststore.inject_into_ssl()

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv
import os

load_dotenv()

credentials = os.getenv("GIGACHAT_CREDENTIALS")
scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

if not credentials:
    raise ValueError("Не найден GIGACHAT_CREDENTIALS в файле .env")

print("Подключаемся к GigaChat-3-Ultra...")

client = GigaChat(
    base_url="https://api.giga.chat/v1",
    credentials=credentials,
    scope=scope,
)

prompt = """
Ты — специалист технической поддержки пользователей 1С.

Сейчас мы проводим тест подключения.
Кратко представься и перечисли 3 типа проблем с 1С,
которые ты умеешь помогать диагностировать.
Ответь на вопрос кто правил в Москве с 1569 по 1687 года?
"""

chat = Chat(
    model="GigaChat-3-Ultra",
    messages=[
        Messages(
            role=MessagesRole.USER,
            content=prompt,
        )
    ],
)

response = client.chat(chat)

print("\nОтвет GigaChat:")
print(response.choices[0].message.content)