import logging
import tempfile
import time
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from xlrd import XLRDError

from app.gigachat.errors import to_user_message
from app.files.documents import DocumentProcessor
from app.files.image import ImageProcessor


logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = DocumentProcessor.MAX_FILE_SIZE
Image.MAX_IMAGE_PIXELS = 20000000


def analyze_upload(manager, session_id: str, message: str, upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    is_image = suffix in ImageProcessor.SUPPORTED_EXTENSIONS
    if not is_image and suffix not in DocumentProcessor.SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Этот формат файла не поддерживается.")
    max_bytes = ImageProcessor.MAX_FILE_SIZE if is_image else MAX_UPLOAD_BYTES
    if not message.strip() or len(message) > 12000:
        raise HTTPException(422, "Опишите проблему: от 1 до 12000 символов.")
    with tempfile.TemporaryDirectory(prefix="support-upload-") as directory:
        target = Path(directory) / f"attachment{suffix}"
        total_bytes = 0
        with target.open("wb") as destination:
            while chunk := upload.file.read(65536):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(413, f"Размер файла не должен превышать {max_bytes // (1024 * 1024)} МБ.")
                destination.write(chunk)
        if not total_bytes:
            raise HTTPException(422, "Файл пустой.")
        if is_image:
            try:
                with Image.open(target) as screenshot:
                    expected_format = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}[suffix]
                    if screenshot.format != expected_format or screenshot.width * screenshot.height > Image.MAX_IMAGE_PIXELS:
                        raise HTTPException(415, "Неподдерживаемый формат или слишком большое разрешение изображения.")
                    screenshot.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as failure:
                raise HTTPException(415, "Не удалось прочитать изображение PNG, JPEG или WebP.") from failure
        session = manager.get_or_create(session_id)
        with session._lock:
            request_id = None
            started_at = time.monotonic()
            if session.db and session.user_id:
                try:
                    request_id = session.db.create_request(user_id=session.user_id, question=message, channel="web", category="Анализ изображения" if is_image else "Анализ документа")
                    session.last_request_id = request_id
                except Exception:
                    logger.exception("Не удалось записать обращение с файлом")
            try:
                answer = session.analyze_file(str(target), message)
            except Exception as failure:
                if request_id:
                    try:
                        session.db.complete_request(request_id, "", status="failed", response_time_ms=int((time.monotonic() - started_at) * 1000))
                    except Exception:
                        logger.exception("Не удалось записать ошибку анализа")
                if isinstance(failure, (ValueError, UnicodeError, BadZipFile, ParseError, XLRDError, KeyError)):
                    raise HTTPException(422, "Не удалось прочитать документ: проверьте формат, размер и отсутствие защиты паролем.") from failure
                logger.exception("Ошибка анализа файла")
                raise HTTPException(502, to_user_message(failure)) from failure
            if request_id:
                try:
                    session.db.complete_request(request_id, answer, status="failed" if session.last_request_failed else "success", response_time_ms=int((time.monotonic() - started_at) * 1000))
                except Exception:
                    logger.exception("Не удалось сохранить результат анализа")
            if session.last_request_failed:
                raise HTTPException(502, answer)
            return answer
