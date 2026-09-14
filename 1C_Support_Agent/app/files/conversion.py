import csv
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import xlrd
from striprtf.striprtf import rtf_to_text


MAX_DOCUMENT_BYTES = 40 * 1024 * 1024


def decode_text(content: bytes) -> str:
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        return content.decode('utf-16')
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return content.decode('cp1251')


def convert_text(source: Path, target: Path) -> None:
    text = decode_text(source.read_bytes())
    if '\x00' in text:
        raise ValueError('Вместо текстового документа получены двоичные данные.')
    target.write_text(text, encoding='utf-8')


def convert_rtf(source: Path, target: Path) -> None:
    content = source.read_bytes().decode('latin-1')
    if not content.lstrip().startswith('{\\rtf'):
        raise ValueError('Не удалось прочитать документ RTF.')
    target.write_text(rtf_to_text(content), encoding='utf-8')


def convert_open_document(source: Path, target: Path) -> None:
    with ZipFile(source) as archive:
        entry = archive.getinfo('content.xml')
        if entry.file_size > MAX_DOCUMENT_BYTES:
            raise ValueError('Распакованное содержимое документа превышает 40 МБ.')
        with archive.open(entry) as content, target.open('w', encoding='utf-8') as output:
            for event, element in ElementTree.iterparse(content, events=('start', 'end')):
                tag = element.tag.rsplit('}', 1)[-1]
                if event == 'start' and tag in {'table', 'page'}:
                    names = [value for name, value in element.attrib.items() if name.endswith('}name')]
                    output.write('\n' + ' '.join(names) + '\n')
                if event == 'end' and tag in {'p', 'h'}:
                    output.write(''.join(element.itertext()) + '\n')
                    element.clear()


def convert_legacy_spreadsheet(source: Path, target: Path) -> None:
    with xlrd.open_workbook(str(source), on_demand=True) as workbook:
        with target.open('w', encoding='utf-8', newline='') as output:
            writer = csv.writer(output, delimiter='\t')
            for sheet in workbook.sheets():
                writer.writerow([f'Лист: {sheet.name}'])
                for row_index in range(sheet.nrows):
                    values = []
                    for cell in sheet.row(row_index):
                        value = cell.value
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate_as_datetime(value, workbook.datemode).isoformat()
                        values.append(value)
                    writer.writerow(values)


class DocumentPreparer:
    NATIVE_EXTENSIONS = frozenset({'.doc', '.docx', '.pdf', '.epub', '.ppt', '.pptx', '.xlsx'})
    ALIASES = {'.xlsm': '.xlsx', '.xltx': '.xlsx', '.pps': '.ppt', '.ppsx': '.pptx'}
    CONVERTERS = {
        '.rtf': convert_rtf,
        '.odt': convert_open_document,
        '.ods': convert_open_document,
        '.odp': convert_open_document,
        '.xls': convert_legacy_spreadsheet,
        '.xlt': convert_legacy_spreadsheet,
    }

    @classmethod
    @contextmanager
    def prepare(cls, source: Path):
        extension = source.suffix.lower()
        if extension in cls.NATIVE_EXTENSIONS:
            yield source
            return
        with tempfile.TemporaryDirectory(prefix='support-document-') as directory:
            target = Path(directory) / ('document' + cls.ALIASES.get(extension, '.txt'))
            if extension in cls.ALIASES:
                shutil.copyfile(source, target)
            else:
                converter = cls.CONVERTERS.get(extension, convert_text)
                converter(source, target)
            if not target.stat().st_size:
                raise ValueError('В документе не найдено текста для анализа.')
            if target.stat().st_size > MAX_DOCUMENT_BYTES:
                raise ValueError('После преобразования документ превышает лимит GigaChat 40 МБ.')
            yield target
