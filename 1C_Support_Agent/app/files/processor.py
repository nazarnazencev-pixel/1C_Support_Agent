from pathlib import Path

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.files.documents import DocumentProcessor
from app.files.image import ImageProcessor


class FileProcessor:

    IMAGE_EXTENSIONS = ImageProcessor.SUPPORTED_EXTENSIONS
    DOCUMENT_EXTENSIONS = DocumentProcessor.SUPPORTED_EXTENSIONS

    def __init__(self, client: GigaChat):
        self.client = client

        self.documents = DocumentProcessor(client)
        self.images = ImageProcessor(client)

    def upload(self, file_path: str):
        path = Path(file_path)

        extension = path.suffix.lower()

        if extension in self.IMAGE_EXTENSIONS:
            return self.images.upload(file_path)

        if extension in self.DOCUMENT_EXTENSIONS:
            return self.documents.upload(file_path)

        raise ValueError(
            f"Неподдерживаемый тип файла: {extension}"
        )

    def analyze_image(
        self,
        file_id: str,
        user_message: str,
        model: str,
    ) -> str:

        chat = Chat(
            model=model,
            messages=[
                Messages(
                    role=MessagesRole.USER,
                    content=user_message,
                    attachments=[file_id],
                )
            ],
        )

        response = self.client.chat(chat)

        return response.choices[0].message.content

    def analyze_document(
        self,
        file_id: str,
        user_message: str,
        model: str,
    ) -> str:

        chat = Chat(
            model=model,
            messages=[
                Messages(
                    role=MessagesRole.USER,
                    content=user_message,
                    attachments=[file_id],
                )
            ],
        )

        response = self.client.chat(chat)

        return response.choices[0].message.content
