import hashlib
import re

from dataclasses import dataclass


# Разбиваем документ по markdown-заголовкам ("#", "##", "###", ...).
# Каждый заголовок начинает новый раздел; текст до первого заголовка
# (если он есть) считается отдельным вступительным разделом.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

# Разделы короче этого считаются слишком мелкими, чтобы быть
# самостоятельным чанком для эмбеддинга - без контекста соседних
# абзацев отдельная фраза в 15 слов плохо семантически отличима от
# других похожих фраз. Такие разделы приклеиваются к предыдущему.
_MIN_CHUNK_CHARS = 120

# Разделы длиннее этого режутся по границам абзацев на несколько
# чанков - иначе один длинный раздел документа целиком доминирует над
# остальной базой знаний при поиске и не помещается в бюджет символов
# контекста, который агент подставляет в system prompt.
_MAX_CHUNK_CHARS = 900


@dataclass(frozen=True)
class Chunk:
    """
    Один фрагмент базы знаний, готовый к получению эмбеддинга.

    id - стабильный идентификатор фрагмента (не зависит от позиции
    файла в файловой системе), используется для инкрементального
    переиндексирования: если текст фрагмента не изменился, его id и
    content_hash совпадут с предыдущей сборкой индекса, и повторный
    вызов Embeddings API для него не нужен.
    """

    id: str
    source: str
    heading: str
    text: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            self.text.encode("utf-8")
        ).hexdigest()


def _split_long_section(text: str, max_chars: int) -> list[str]:
    """
    Режет длинный раздел на части по границам пустых строк
    (абзацев), стараясь не превышать max_chars на часть и не резать
    абзац посередине.
    """

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    parts: list[str] = []
    current = ""

    for paragraph in paragraphs:

        candidate = (
            f"{current}\n\n{paragraph}"
            if current
            else paragraph
        )

        if len(candidate) <= max_chars or not current:
            current = candidate
            continue

        parts.append(current)
        current = paragraph

    if current:
        parts.append(current)

    return parts or [text]


def chunk_markdown(
    text: str,
    source: str,
    max_chars: int = _MAX_CHUNK_CHARS,
    min_chars: int = _MIN_CHUNK_CHARS,
) -> list[Chunk]:
    """
    Разбивает содержимое одного файла базы знаний на набор Chunk.

    Стратегия:

    1. Делим текст по markdown-заголовкам - каждый раздел получает
       заголовок ближайшего "#"/"##"/... над ним в качестве контекста
       (по заголовку верхнего уровня, если структура вложенная).
    2. Слишком короткие соседние разделы склеиваются - отдельная
       фраза без контекста плохо ищется по смыслу.
    3. Слишком длинные разделы режутся по границам абзацев.

    Файлы без markdown-заголовков (например, старые .txt-документы)
    целиком становятся одним чанком, если укладываются в max_chars,
    иначе режутся по абзацам как единый безымянный раздел.
    """

    text = text.strip()

    if not text:
        return []

    matches = list(_HEADING_RE.finditer(text))

    # Заголовок документа верхнего уровня (первый "#") используется
    # как общий контекст для разделов без собственного заголовка.
    doc_title = ""
    if matches and matches[0].group(1) == "#":
        doc_title = matches[0].group(2).strip()

    sections: list[tuple[str, str]] = []

    if not matches:
        sections.append(("", text))
    else:
        # Текст до первого заголовка (если есть) - отдельный раздел.
        if matches[0].start() > 0:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                sections.append(("", preamble))

        for index, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )
            body = text[start:end].strip()

            if not body:
                continue

            sections.append((heading, body))

    # Склеиваем слишком короткие разделы с предыдущим.
    merged: list[tuple[str, str]] = []

    for heading, body in sections:

        if (
            merged
            and len(body) < min_chars
        ):
            previous_heading, previous_body = merged[-1]
            merged[-1] = (
                previous_heading,
                f"{previous_body}\n\n{body}",
            )
            continue

        merged.append((heading, body))

    chunks: list[Chunk] = []

    for order, (heading, body) in enumerate(merged):

        parts = (
            _split_long_section(body, max_chars)
            if len(body) > max_chars
            else [body]
        )

        for part_index, part in enumerate(parts):

            display_heading = heading or doc_title or source

            # Заголовок документа/раздела добавляется в сам текст
            # чанка - это даёт эмбеддингу дополнительный семантический
            # якорь (запрос "не проводится документ" должен находить
            # раздел "Типовая причина: недостаточно остатков" не хуже,
            # чем раздел, где эти слова есть дословно в теле).
            prefix_parts = [
                p
                for p in (doc_title, heading)
                if p
            ]
            prefix = " / ".join(dict.fromkeys(prefix_parts))

            chunk_text = (
                f"{prefix}\n\n{part}"
                if prefix
                else part
            )

            chunk_id = hashlib.sha256(
                f"{source}::{order}::{part_index}".encode("utf-8")
            ).hexdigest()[:16]

            chunks.append(
                Chunk(
                    id=chunk_id,
                    source=source,
                    heading=display_heading,
                    text=chunk_text,
                )
            )

    return chunks
