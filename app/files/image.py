from pathlib import Path

from gigachat import GigaChat


class ImageProcessor:

    SUPPORTED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
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

        with path.open("rb") as file:
            uploaded = self.client.upload_file(
                file,
                purpose="general",
            )

        return uploaded