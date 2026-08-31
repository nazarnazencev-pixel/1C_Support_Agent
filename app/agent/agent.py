import truststore

truststore.inject_into_ssl()

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.config.settings import (
    GIGACHAT_BASE_URL,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_SCOPE,
    GIGACHAT_MODEL,
)


SYSTEM_PROMPT = """
Ты — специалист технической поддержки пользователей 1С.

Твоя задача — помогать сотрудникам диагностировать
и решать проблемы, связанные с использованием 1С.

Основные правила:

1. Отвечай профессионально и понятно.
2. Не выдумывай факты.
3. Если информации недостаточно — задавай уточняющие вопросы.
4. Не предлагай потенциально опасные действия без предупреждения.
5. Не рекомендуй удаление данных без явного предупреждения о последствиях.
6. При диагностике сначала собирай необходимые данные.
7. Отделяй достоверную информацию от предположений.
8. Если не уверен в решении — честно сообщи об этом.
9. Предлагай пошаговые инструкции.
10. Учитывай контекст предыдущих сообщений пользователя.

Типичные данные, которые могут потребоваться:

- конфигурация 1С;
- версия конфигурации;
- версия платформы 1С:Предприятие;
- режим работы;
- клиент-серверная или файловая база;
- текст ошибки;
- действия, после которых появилась проблема;
- что уже было сделано для решения проблемы.
"""


class SupportAgent:

    def __init__(self):
        self.client = GigaChat(
            base_url=GIGACHAT_BASE_URL,
            credentials=GIGACHAT_CREDENTIALS,
            scope=GIGACHAT_SCOPE,
        )

        self.history = []

    def ask(self, user_message: str) -> str:

        self.history.append(
            Messages(
                role=MessagesRole.USER,
                content=user_message,
            )
        )

        messages = [
            Messages(
                role=MessagesRole.SYSTEM,
                content=SYSTEM_PROMPT,
            )
        ]

        messages.extend(self.history)

        chat = Chat(
            model=GIGACHAT_MODEL,
            messages=messages,
        )

        response = self.client.chat(chat)

        assistant_message = response.choices[0].message.content

        self.history.append(
            Messages(
                role=MessagesRole.ASSISTANT,
                content=assistant_message,
            )
        )

        return assistant_message