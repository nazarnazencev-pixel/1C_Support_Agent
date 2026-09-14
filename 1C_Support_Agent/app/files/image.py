import tempfile
from pathlib import Path

from PIL import Image


class ImageProcessor:
    SUPPORTED_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.webp'})
    MAX_FILE_SIZE = 15 * 1024 * 1024

    def __init__(self, client):
        self.client = client

    def upload(self, file_path: str):
        path = Path(file_path)
        if not path.is_file():
            raise ValueError('Изображение не найдено.')
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError('Неподдерживаемый формат изображения.')
        if not 0 < path.stat().st_size <= self.MAX_FILE_SIZE:
            raise ValueError('Размер изображения должен быть от 1 байта до 15 МБ.')
        with tempfile.TemporaryDirectory(prefix='support-image-') as directory:
            if path.suffix.lower() == '.webp':
                target = Path(directory) / 'image.png'
                with Image.open(path) as image:
                    image.save(target, format='PNG')
                if target.stat().st_size > self.MAX_FILE_SIZE:
                    raise ValueError('После преобразования изображение превышает 15 МБ.')
                path = target
            with path.open('rb') as image_file:
                return self.client.upload(image_file, purpose='general')
