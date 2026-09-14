"""
Сборка векторного индекса базы знаний.

Запуск:

    python scripts/build_knowledge_index.py
    python scripts/build_knowledge_index.py --dry-run
    python scripts/build_knowledge_index.py --knowledge-path data/knowledge \\
        --index-path data/knowledge/index

Скрипт читает все .md/.txt файлы из папки базы знаний, разбивает их
на чанки (app.knowledge.chunking), получает эмбеддинги через GigaChat
Embeddings API и сохраняет результат в index-path в виде двух файлов:

    vectors.npy - массив float32 (N x D), по одной строке на чанк;
    meta.json   - {"model", "built_at", "dim", "chunks": [...]},
                  где chunks[i] соответствует строке i в vectors.npy.

Инкрементальность: если чанк с тем же содержимым (тем же
sha256-хэшем текста) уже был в предыдущей сборке индекса, его вектор
переиспользуется без повторного обращения к Embeddings API. Это
держит время и стоимость пересборки пропорциональными объёму
РЕАЛЬНО изменившегося контента, а не всей базе знаний - важно, так
как база знаний ожидаемо растёт со временем, а перегенерировать
эмбеддинг каждой статьи заново при любой мелкой правке в одной из
них не нужно.

Запускать этот скрипт нужно офлайн, отдельно от обработки живых
запросов пользователей - именно поэтому агент (VectorKnowledgeBase)
сам никогда не пытается построить или перестроить индекс, а только
читает уже готовый результат.
"""

import argparse
import json
import logging
import sys
import time

from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge.chunking import Chunk, chunk_markdown  # noqa: E402


logger = logging.getLogger(__name__)

_KNOWLEDGE_EXTENSIONS = {".md", ".txt"}
_DEFAULT_BATCH_SIZE = 16


def discover_documents(
    knowledge_path: Path,
    index_path: Path,
) -> list[Path]:
    """
    Возвращает отсортированный список файлов базы знаний.

    Файлы внутри index_path (сам индекс) исключаются - на случай,
    если index_path вложен в knowledge_path (значение по умолчанию -
    data/knowledge/index внутри data/knowledge).
    """

    if not knowledge_path.exists():
        return []

    resolved_index_path = index_path.resolve()

    documents = []

    for file_path in knowledge_path.rglob("*"):

        if file_path.suffix.lower() not in _KNOWLEDGE_EXTENSIONS:
            continue

        if not file_path.is_file():
            continue

        resolved = file_path.resolve()

        if resolved_index_path in resolved.parents:
            continue

        documents.append(file_path)

    return sorted(documents)


def build_chunks(
    knowledge_path: Path,
    index_path: Path,
) -> list[Chunk]:
    """
    Читает документы базы знаний и разбивает их на чанки.

    Файлы, которые не удалось прочитать как текст (битая кодировка,
    исчезли между discover и чтением), пропускаются с предупреждением
    - одна проблемная статья не должна останавливать сборку всего
    индекса.
    """

    chunks: list[Chunk] = []

    for file_path in discover_documents(knowledge_path, index_path):

        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning(
                "Пропускаю %s: не удалось прочитать (%s)",
                file_path,
                exc,
            )
            continue

        chunks.extend(
            chunk_markdown(text, source=str(file_path))
        )

    return chunks


def load_previous_vectors(index_path: Path) -> dict[str, list[float]]:
    """
    Возвращает {content_hash: vector} из предыдущей сборки индекса,
    если она есть, иначе пустой словарь.

    content_hash - это Chunk.content_hash (sha256 текста чанка), а
    не id чанка: id зависит от позиции раздела в файле и меняется
    при правках соседних разделов документа, а хэш содержимого - нет,
    поэтому именно он определяет, можно ли переиспользовать вектор.
    """

    vectors_file = index_path / "vectors.npy"
    meta_file = index_path / "meta.json"

    if not vectors_file.exists() or not meta_file.exists():
        return {}

    try:
        vectors = np.load(vectors_file)
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Не удалось прочитать предыдущий индекс в %s (%s) - "
            "переиндексирую всё с нуля.",
            index_path,
            exc,
        )
        return {}

    previous: dict[str, list[float]] = {}

    for chunk_meta, vector in zip(meta.get("chunks", []), vectors):
        chunk_hash = chunk_meta.get("hash")
        if chunk_hash:
            previous[chunk_hash] = vector.tolist()

    return previous


def partition_chunks(
    chunks: list[Chunk],
    previous_vectors: dict[str, list[float]],
) -> tuple[list[Chunk], int]:
    """
    Делит чанки на те, для которых нужен новый вызов Embeddings API,
    и те, чей вектор можно переиспользовать из предыдущей сборки.

    Возвращает (чанки_без_вектора, количество_переиспользованных).
    """

    to_embed = [
        chunk
        for chunk in chunks
        if chunk.content_hash not in previous_vectors
    ]

    reused_count = len(chunks) - len(to_embed)

    return to_embed, reused_count


def embed_texts(
    client,
    texts: list[str],
    model: str,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> list[list[float]]:
    """
    Получает эмбеддинги для списка текстов батчами.

    Каждый батч отправляется отдельным вызовом Embeddings API.
    Результат внутри батча переупорядочивается по полю index ответа
    API - на случай, если сервис вернёт эмбеддинги не строго в
    порядке входных текстов.
    """

    all_vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]

        response = client.embeddings(batch, model=model)

        ordered = sorted(response.data, key=lambda item: item.index)

        all_vectors.extend(item.embedding for item in ordered)

        logger.info(
            "Эмбеддинги: обработано %d/%d чанков",
            min(start + batch_size, len(texts)),
            len(texts),
        )

    return all_vectors


def build_index(
    knowledge_path: str = "data/knowledge",
    index_path: str = "data/knowledge/index",
    client=None,
    model: str = "Embeddings",
    batch_size: int = _DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> dict:
    """
    Основной сценарий сборки индекса. Возвращает сводку по сборке
    (используется и для вывода в консоль, и в тестах).
    """

    started_at = time.monotonic()

    knowledge_dir = Path(knowledge_path)
    index_dir = Path(index_path)

    chunks = build_chunks(knowledge_dir, index_dir)

    if not chunks:
        logger.warning(
            "В %s не найдено ни одного .md/.txt документа - "
            "индекс не строится.",
            knowledge_dir,
        )
        return {
            "chunk_count": 0,
            "reused_count": 0,
            "embedded_count": 0,
            "dry_run": dry_run,
        }

    previous_vectors = load_previous_vectors(index_dir)
    to_embed, reused_count = partition_chunks(chunks, previous_vectors)

    summary = {
        "chunk_count": len(chunks),
        "reused_count": reused_count,
        "embedded_count": len(to_embed),
        "dry_run": dry_run,
    }

    logger.info(
        "Найдено чанков: %d (переиспользуется: %d, "
        "требует нового эмбеддинга: %d)",
        len(chunks),
        reused_count,
        len(to_embed),
    )

    if dry_run:
        return summary

    new_vectors_by_hash: dict[str, list[float]] = {}

    if to_embed:
        if client is None:
            from app.gigachat.client import GigaChatClient

            client = GigaChatClient(timeout=30.0, max_retries=1)

        embedded = embed_texts(
            client,
            [chunk.text for chunk in to_embed],
            model=model,
            batch_size=batch_size,
        )

        for chunk, vector in zip(to_embed, embedded):
            new_vectors_by_hash[chunk.content_hash] = vector

    vectors: list[list[float]] = []
    chunk_meta: list[dict] = []

    for chunk in chunks:
        vector = (
            previous_vectors.get(chunk.content_hash)
            or new_vectors_by_hash.get(chunk.content_hash)
        )

        if vector is None:
            # Не должно происходить - страхуемся явной ошибкой
            # вместо тихого рассинхрона vectors.npy/meta.json.
            raise RuntimeError(
                f"Не найден вектор для чанка {chunk.id} "
                f"из {chunk.source}"
            )

        vectors.append(vector)
        chunk_meta.append(
            {
                "id": chunk.id,
                "file": chunk.source,
                "heading": chunk.heading,
                "text": chunk.text,
                "hash": chunk.content_hash,
            }
        )

    vectors_array = np.array(vectors, dtype=np.float32)

    index_dir.mkdir(parents=True, exist_ok=True)

    np.save(index_dir / "vectors.npy", vectors_array)

    (index_dir / "meta.json").write_text(
        json.dumps(
            {
                "model": model,
                "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "dim": vectors_array.shape[1],
                "chunk_count": len(chunk_meta),
                "chunks": chunk_meta,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    elapsed = time.monotonic() - started_at
    summary["elapsed_seconds"] = elapsed

    logger.info(
        "Индекс сохранён в %s (%d чанков, %.1f сек, "
        "новых эмбеддингов: %d, переиспользовано: %d)",
        index_dir,
        len(chunk_meta),
        elapsed,
        len(to_embed),
        reused_count,
    )

    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сборка векторного индекса базы знаний 1С."
    )

    parser.add_argument(
        "--knowledge-path",
        default="data/knowledge",
        help="Папка с исходными документами базы знаний.",
    )
    parser.add_argument(
        "--index-path",
        default="data/knowledge/index",
        help="Куда сохранить vectors.npy и meta.json.",
    )
    parser.add_argument(
        "--model",
        default="Embeddings",
        help="Название модели эмбеддингов GigaChat.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help="Сколько чанков отправлять в одном вызове API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Показать, сколько чанков будет проиндексировано/"
            "переиспользовано, без обращения к Embeddings API и "
            "без записи файлов индекса."
        ),
    )

    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = _parse_args()

    if not args.dry_run:
        from app.config.settings import validate_config

        validate_config()

    summary = build_index(
        knowledge_path=args.knowledge_path,
        index_path=args.index_path,
        model=args.model,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    if summary["chunk_count"] == 0:
        sys.exit(1)

    if args.dry_run:
        print(
            f"Чанков всего: {summary['chunk_count']}\n"
            f"Будет переиспользовано: {summary['reused_count']}\n"
            f"Будет отправлено на эмбеддинг: "
            f"{summary['embedded_count']}"
        )


if __name__ == "__main__":
    main()
