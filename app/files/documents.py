from pathlib import Path
from typing import Final

from gigachat import GigaChat


class DocumentProcessor:
    """
    Обработчик документов для GigaChat.

    Отвечает за:
    - проверку существования файла;
    - проверку типа файла;
    - проверку размера;
    - загрузку файла в GigaChat.

    Анализ содержимого документа выполняется
    на следующем уровне приложения.
    """

    # =========================================================
    # Текстовые документы
    # =========================================================

    TEXT_EXTENSIONS: Final[frozenset[str]] = frozenset({
        ".txt",
        ".md",
        ".markdown",
        ".log",
        ".csv",
        ".tsv",
        ".json",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
    })

    # =========================================================
    # Документы
    # =========================================================

    DOCUMENT_EXTENSIONS: Final[frozenset[str]] = frozenset({
        ".doc",
        ".docx",
        ".pdf",
        ".rtf",
        ".odt",
        ".epub",
    })

    # =========================================================
    # Электронные таблицы
    # =========================================================

    SPREADSHEET_EXTENSIONS: Final[frozenset[str]] = frozenset({
        ".xls",
        ".xlsx",
        ".xlsm",
        ".xlt",
        ".xltx",
        ".ods",
    })

    # =========================================================
    # Презентации
    # =========================================================

    PRESENTATION_EXTENSIONS: Final[frozenset[str]] = frozenset({
        ".ppt",
        ".pptx",
        ".pps",
        ".ppsx",
        ".odp",
    })

    # =========================================================
    # Все поддерживаемые расширения
    # =========================================================

    SUPPORTED_EXTENSIONS: Final[frozenset[str]] = (
        TEXT_EXTENSIONS
        | DOCUMENT_EXTENSIONS
        | SPREADSHEET_EXTENSIONS
        | PRESENTATION_EXTENSIONS
    )

    # =========================================================
    # Ограничение размера
    # =========================================================

    # 50 MB.
    #
    # Значение можно изменить после того, как определимся
    # с реальными ограничениями GigaChat/API.
    MAX_FILE_SIZE: Final[int] = 50 * 1024 * 1024

    def __init__(self, client: GigaChat):
        """
        Создаёт обработчик документов.

        client:
            экземпляр GigaChat.
        """

        if client is None:
            raise ValueError(
                "client не может быть None"
            )

        self.client = client

    # =========================================================
    # Расширение
    # =========================================================

    @staticmethod
    def get_extension(
        file_path: str | Path,
    ) -> str:
        """
        Возвращает расширение файла в нижнем регистре.

        Например:

            report.PDF -> ".pdf"
            TEST.XLSX -> ".xlsx"
        """

        path = Path(file_path)

        return path.suffix.lower()

    # =========================================================
    # Проверка поддержки
    # =========================================================

    @classmethod
    def is_supported(
        cls,
        file_path: str | Path,
    ) -> bool:
        """
        Проверяет, поддерживается ли расширение файла.
        """

        extension = cls.get_extension(
            file_path
        )

        return extension in cls.SUPPORTED_EXTENSIONS

    # =========================================================
    # Тип документа
    # =========================================================

    @classmethod
    def get_file_type(
        cls,
        file_path: str | Path,
    ) -> str:
        """
        Возвращает категорию файла.

        Возможные значения:

            text
            document
            spreadsheet
            presentation
            unknown
        """

        extension = cls.get_extension(
            file_path
        )

        if extension in cls.TEXT_EXTENSIONS:
            return "text"

        if extension in cls.DOCUMENT_EXTENSIONS:
            return "document"

        if extension in cls.SPREADSHEET_EXTENSIONS:
            return "spreadsheet"

        if extension in cls.PRESENTATION_EXTENSIONS:
            return "presentation"

        return "unknown"

    # =========================================================
    # Проверка файла
    # =========================================================

    def validate(
        self,
        file_path: str | Path,
    ) -> Path:
        """
        Проверяет файл перед загрузкой.

        Возвращает нормализованный Path.

        Возможные ошибки:
        - файл не существует;
        - путь указывает не на файл;
        - файл пустой;
        - формат не поддерживается;
        - файл слишком большой.
        """

        path = Path(file_path)

        # -----------------------------------------------------
        # Проверяем существование
        # -----------------------------------------------------

        if not path.exists():
            raise FileNotFoundError(
                f"Файл не найден: {path}"
            )

        # -----------------------------------------------------
        # Проверяем, что это именно файл
        # -----------------------------------------------------

        if not path.is_file():
            raise ValueError(
                f"Указанный путь не является файлом: {path}"
            )

        # -----------------------------------------------------
        # Проверяем расширение
        # -----------------------------------------------------

        extension = path.suffix.lower()

        if not extension:
            raise ValueError(
                f"Файл не имеет расширения: {path.name}"
            )

        if extension not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(
                sorted(self.SUPPORTED_EXTENSIONS)
            )

            raise ValueError(
                f"Неподдерживаемый формат файла: "
                f"{extension}\n"
                f"Поддерживаемые форматы: {supported}"
            )

        # -----------------------------------------------------
        # Проверяем размер
        # -----------------------------------------------------

        file_size = path.stat().st_size

        if file_size == 0:
            raise ValueError(
                f"Файл пустой: {path.name}"
            )

        if file_size > self.MAX_FILE_SIZE:
            size_mb = file_size / (
                1024 * 1024
            )

            max_size_mb = self.MAX_FILE_SIZE / (
                1024 * 1024
            )

            raise ValueError(
                f"Файл слишком большой: "
                f"{size_mb:.2f} MB. "
                f"Максимальный размер: "
                f"{max_size_mb:.0f} MB."
            )

        return path

    # =========================================================
    # Загрузка
    # =========================================================

    def upload(
        self,
        file_path: str | Path,
    ):
        """
        Проверяет и загружает документ в GigaChat.

        Возвращает объект, полученный от GigaChat.
        """

        path = self.validate(
            file_path
        )

        # client.upload() (не upload_file() напрямую) - чтобы сетевые
        # ошибки/timeout/авторизация проходили через нормализацию
        # GigaChatClient (см. app/gigachat/client.py).
        with path.open(
            "rb"
        ) as file:

            uploaded = self.client.upload(
                file,
                purpose="general",
            )

        return uploaded