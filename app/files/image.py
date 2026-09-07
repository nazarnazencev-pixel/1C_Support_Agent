from pathlib import Path

from gigachat import GigaChat


class ImageProcessor:

    SUPPORTED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }

    def __init__(self, client: GigaChat):
        self.client = client

    def upload(self, file_path: str):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Файл не найден: {file_path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Неподдерживаемый формат изображения: {path.suffix}"
            )

        # Используем client.upload(), а не client.upload_file() напрямую:
        # upload() - это метод-обёртка GigaChatClient с нормализацией
        # сетевых ошибок/timeout/авторизации в наши исключения
        # (см. app/gigachat/client.py). Прямой вызов upload_file()
        # эту обработку минует.
        with path.open("rb") as file:
            uploaded = self.client.upload(
                file,
                purpose="general",
            )

        return uploaded