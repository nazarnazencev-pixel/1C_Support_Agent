from pathlib import Path
from typing import Final

from app.files.conversion import DocumentPreparer, MAX_DOCUMENT_BYTES


class DocumentProcessor:
    TEXT_EXTENSIONS: Final = frozenset({
        '.txt', '.md', '.markdown', '.log', '.csv', '.tsv', '.json', '.xml',
        '.html', '.htm', '.css', '.yaml', '.yml', '.ini', '.cfg', '.conf',
    })
    DOCUMENT_EXTENSIONS: Final = frozenset({'.doc', '.docx', '.pdf', '.rtf', '.odt', '.epub'})
    SPREADSHEET_EXTENSIONS: Final = frozenset({'.xls', '.xlsx', '.xlsm', '.xlt', '.xltx', '.ods'})
    PRESENTATION_EXTENSIONS: Final = frozenset({'.ppt', '.pptx', '.pps', '.ppsx', '.odp'})
    SUPPORTED_EXTENSIONS: Final = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | SPREADSHEET_EXTENSIONS | PRESENTATION_EXTENSIONS
    MAX_FILE_SIZE: Final = MAX_DOCUMENT_BYTES

    def __init__(self, client):
        if client is None:
            raise ValueError('client не может быть None')
        self.client = client

    @staticmethod
    def get_extension(file_path: str | Path) -> str:
        return Path(file_path).suffix.lower()

    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        return cls.get_extension(file_path) in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_file_type(cls, file_path: str | Path) -> str:
        extension = cls.get_extension(file_path)
        categories = {
            'text': cls.TEXT_EXTENSIONS,
            'document': cls.DOCUMENT_EXTENSIONS,
            'spreadsheet': cls.SPREADSHEET_EXTENSIONS,
            'presentation': cls.PRESENTATION_EXTENSIONS,
        }
        return next((name for name, extensions in categories.items() if extension in extensions), 'unknown')

    def validate(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        if not path.is_file():
            raise ValueError('Документ не найден.')
        if not self.is_supported(path):
            raise ValueError(f'Неподдерживаемый формат документа: {path.suffix}')
        if not path.stat().st_size:
            raise ValueError('Файл пустой.')
        if path.stat().st_size > self.MAX_FILE_SIZE:
            raise ValueError('Размер документа не должен превышать 40 МБ.')
        return path

    def upload(self, file_path: str | Path):
        path = self.validate(file_path)
        with DocumentPreparer.prepare(path) as prepared:
            with prepared.open('rb') as document:
                return self.client.upload(document, purpose='general')
