from unittest.mock import MagicMock
import pytest
from app.files.documents import DocumentProcessor
from app.files.image import ImageProcessor


def test_document_processor_validation(tmp_path):
    client = MagicMock()
    doc_processor = DocumentProcessor(client)

    doc_file = tmp_path / "test_doc.txt"
    doc_file.write_text("Тестовый лог ошибки 1С", encoding="utf-8")

    validated_path = doc_processor.validate(str(doc_file))
    assert validated_path == doc_file

    unsupported_file = tmp_path / "test_doc.unknown"
    unsupported_file.write_text("data", encoding="utf-8")

    with pytest.raises(ValueError, match="Неподдерживаемый формат"):
        doc_processor.validate(str(unsupported_file))


def test_document_processor_upload_uses_normalized_client(tmp_path):
    client = MagicMock()
    doc_processor = DocumentProcessor(client)

    doc_file = tmp_path / "test_doc.txt"
    doc_file.write_text("Тестовый лог ошибки 1С", encoding="utf-8")

    # Загрузка должна идти через client.upload() (обёртку
    # GigaChatClient с нормализацией ошибок), а не через
    # client.upload_file() напрямую.
    client.upload.return_value = MagicMock(id_="doc_123")
    uploaded = doc_processor.upload(str(doc_file))

    assert uploaded.id_ == "doc_123"
    client.upload.assert_called_once()
    client.upload_file.assert_not_called()


def test_image_processor_validation(tmp_path):
    client = MagicMock()
    img_processor = ImageProcessor(client)

    img_file = tmp_path / "test_img.png"
    img_file.write_bytes(b"png_data")

    # Загрузка должна идти через client.upload() (обёртку
    # GigaChatClient с нормализацией ошибок), а не через
    # client.upload_file() напрямую.
    client.upload.return_value = MagicMock(id_="img_123")
    uploaded = img_processor.upload(str(img_file))

    assert uploaded.id_ == "img_123"
    client.upload.assert_called_once()
    client.upload_file.assert_not_called()


def test_image_processor_supports_webp(tmp_path):
    client = MagicMock()
    img_processor = ImageProcessor(client)

    img_file = tmp_path / "test_img.webp"
    img_file.write_bytes(b"webp_data")

    client.upload.return_value = MagicMock(id_="img_456")
    uploaded = img_processor.upload(str(img_file))

    assert uploaded.id_ == "img_456"
