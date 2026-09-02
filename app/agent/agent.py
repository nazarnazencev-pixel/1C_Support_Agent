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

from app.knowledge.base import LocalKnowledgeBase
from app.files.processor import FileProcessor

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

        self.knowledge_base = LocalKnowledgeBase()

        self.file_processor = FileProcessor(self.client)

    def ask(self, user_message: str) -> str:

        # Ищем информацию в базе знаний
        knowledge_results = self.knowledge_base.search(
            user_message,
            limit=3,
        )

        knowledge_context = ""

        if knowledge_results:
            knowledge_context = "\n\n".join(
                result["content"]
                for result in knowledge_results
            )

        # Добавляем сообщение пользователя в историю
        self.history.append(
            Messages(
                role=MessagesRole.USER,
                content=user_message,
            )
        )

        # Формируем системный промпт
        system_prompt = SYSTEM_PROMPT

        if knowledge_context:
            system_prompt += f"""

Информация из внутренней базы знаний:

---
{knowledge_context}
---

Используй эту информацию при подготовке ответа.

Если информации из базы знаний недостаточно,
не выдумывай недостающие сведения.
Задай пользователю уточняющие вопросы.
"""

        # Формируем сообщения для GigaChat
        messages = [
            Messages(
                role=MessagesRole.SYSTEM,
                content=system_prompt,
            )
        ]

        messages.extend(self.history)

        # Создаём запрос
        chat = Chat(
            model=GIGACHAT_MODEL,
            messages=messages,
        )

        # Отправляем запрос в GigaChat
        response = self.client.chat(chat)

        assistant_message = response.choices[0].message.content

        # Сохраняем ответ в историю
        self.history.append(
            Messages(
                role=MessagesRole.ASSISTANT,
                content=assistant_message,
            )
        )

        return assistant_message

    def analyze_file(
        self,
        file_path: str,
        user_message: str,
    ) -> str:

        uploaded = self.file_processor.upload(file_path)

        file_id = uploaded.id_

        extension = file_path.lower().split(".")[-1]

        if extension in {"png", "jpg", "jpeg"}:
            return self.file_processor.analyze_image(
                file_id=file_id,
                user_message=user_message,
                model=GIGACHAT_MODEL,
            )

        return self.file_processor.analyze_document(
            file_id=file_id,
            user_message=user_message,
            model=GIGACHAT_MODEL,
        )