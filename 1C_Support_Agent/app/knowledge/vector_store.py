import json
import logging
import threading
import time

from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.knowledge.base import KnowledgeBase, LocalKnowledgeBase


logger = logging.getLogger(__name__)


# =============================================================
# Общий по процессу кэш загруженных индексов.
#
# SupportAgent создаётся заново на каждую сессию (см.
# app/session). Если каждый экземпляр VectorKnowledgeBase будет
# сам читать vectors.npy/meta.json с диска и держать собственную
# копию массива в памяти - при N параллельных сессиях получаем
# N копий одного и того же индекса в памяти и N обращений к диску
# на старте каждой сессии. Индекс меняется только при пересборке
# (см. scripts/build_knowledge_index.py), поэтому его достаточно
# читать один раз на процесс и переиспользовать, пока файлы на
# диске не изменились.
# =============================================================

_index_cache_lock = threading.Lock()
_index_cache: dict[str, tuple[float, list[dict], "np.ndarray"]] = {}


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


class _TTLCache:
    """
    Маленький кэш эмбеддингов запроса с ограничением по размеру и
    времени жизни записи.

    Назначение - не тратить сетевой вызов к Embeddings API повторно
    на один и тот же (или почти сразу повторённый) вопрос
    пользователя в рамках одного обращения: пользователи нередко
    присылают уточнение, начинающееся с той же фразы, или агент может
    быть вызван повторно на том же сообщении при ретрае на уровне
    выше. TTL защищает от неограниченного роста и от использования
    устаревшего эмбеддинга, если модель эмбеддингов когда-нибудь
    поменяется без перезапуска процесса.
    """

    def __init__(self, max_size: int = 256, ttl_seconds: float = 600.0):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, np.ndarray]] = {}

    def get(self, key: str) -> Optional[np.ndarray]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            timestamp, vector = entry
            if time.monotonic() - timestamp > self._ttl_seconds:
                self._store.pop(key, None)
                return None
            return vector

    def set(self, key: str, vector: np.ndarray) -> None:
        with self._lock:
            if (
                len(self._store) >= self._max_size
                and key not in self._store
            ):
                # Простое вытеснение самой старой записи - для
                # кэша эмбеддингов запросов размера в сотни записей
                # точный LRU не даёт заметного выигрыша по сравнению
                # с вытеснением по времени создания.
                oldest_key = min(
                    self._store,
                    key=lambda k: self._store[k][0],
                )
                self._store.pop(oldest_key, None)

            self._store[key] = (time.monotonic(), vector)


def _load_index_from_disk(
    index_path: Path,
) -> Optional[tuple[list[dict], np.ndarray]]:
    """
    Читает vectors.npy + meta.json из index_path.

    Возвращает None, если индекс отсутствует или повреждён/
    несогласован - в этом случае VectorKnowledgeBase должен
    прозрачно работать так, как будто векторного индекса нет
    (полагаясь на LocalKnowledgeBase), а не падать с ошибкой.
    """

    vectors_file = index_path / "vectors.npy"
    meta_file = index_path / "meta.json"

    if not vectors_file.exists() or not meta_file.exists():
        return None

    try:
        vectors = np.load(vectors_file)
        meta_raw = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Не удалось прочитать индекс базы знаний в %s: %s",
            index_path,
            exc,
        )
        return None

    chunks = meta_raw.get("chunks", [])

    if len(chunks) != len(vectors):
        logger.warning(
            "Индекс базы знаний в %s повреждён: "
            "%d векторов, но %d записей метаданных.",
            index_path,
            len(vectors),
            len(chunks),
        )
        return None

    if vectors.size == 0:
        return None

    return chunks, _normalize_rows(vectors.astype(np.float32))


def _get_cached_index(
    index_path: Path,
) -> Optional[tuple[list[dict], np.ndarray]]:
    """
    Возвращает (meta, vectors) из общего кэша процесса, перечитывая
    файлы с диска заново только если индекс ещё не загружался или
    файлы были пересобраны (изменился mtime meta.json) с прошлой
    загрузки.
    """

    key = str(index_path.resolve())
    meta_file = index_path / "meta.json"

    try:
        current_mtime = meta_file.stat().st_mtime
    except OSError:
        with _index_cache_lock:
            _index_cache.pop(key, None)
        return None

    with _index_cache_lock:
        cached = _index_cache.get(key)

    if cached is not None and cached[0] == current_mtime:
        return cached[1], cached[2]

    loaded = _load_index_from_disk(index_path)

    if loaded is None:
        return None

    chunks, vectors = loaded

    with _index_cache_lock:
        _index_cache[key] = (current_mtime, chunks, vectors)

    return chunks, vectors


class VectorKnowledgeBase(KnowledgeBase):
    """
    База знаний с поиском по смысловой близости (эмбеддинги).

    Векторы документов считаются заранее, офлайн, скриптом
    scripts/build_knowledge_index.py, и просто читаются с диска при
    старте (быстро, без сети). В рантайме на каждый вопрос
    пользователя выполняется:

        1. один короткий сетевой вызов Embeddings API GigaChat, чтобы
           получить вектор запроса (с отдельным, заведомо небольшим
           таймаутом - см. embedding_timeout);
        2. локальное сравнение этого вектора со всеми векторами
           документов через numpy (косинусное сходство), без
           обращения к сети - для реалистичного размера базы знаний
           поддержки это заведомо доли миллисекунды.

    Если индекс не собран, повреждён, устарел настолько, что не
    удаётся его прочитать, либо вызов Embeddings API не успел за
    отведённый бюджет времени или завершился ошибкой - поиск не
    падает, а прозрачно откатывается на LocalKnowledgeBase (поиск по
    псевдо-основам слов). Это гарантирует, что база знаний никогда не
    станет причиной превышения бюджета времени на ответ агента: в
    худшем случае агент получит менее точный, но всё же полезный
    контекст, а не зависнет и не откажет пользователю в ответе.
    """

    def __init__(
        self,
        knowledge_path: str = "data/knowledge",
        index_path: str = "data/knowledge/index",
        gigachat_client: Any = None,
        embedding_model: str = "Embeddings",
        embedding_timeout: float = 1.5,
        min_score: float = 0.15,
        query_cache_size: int = 256,
        query_cache_ttl: float = 600.0,
        fallback: Optional[KnowledgeBase] = None,
    ):
        self.knowledge_path = Path(knowledge_path)
        self.index_path = Path(index_path)

        # Клиент GigaChat создаётся лениво (см. _get_client), а не
        # здесь - конструктор VectorKnowledgeBase не должен требовать
        # настроенных credentials и не должен обращаться к сети:
        # SupportAgent создаётся на каждую сессию, и юнит-тесты
        # создают его без реальных credentials.
        self._client = gigachat_client
        self._own_client = gigachat_client is not None

        self.embedding_model = embedding_model
        self.embedding_timeout = embedding_timeout
        self.min_score = min_score

        self._query_cache = _TTLCache(
            max_size=query_cache_size,
            ttl_seconds=query_cache_ttl,
        )

        self._fallback = fallback or LocalKnowledgeBase(
            str(knowledge_path)
        )

    # =========================================================
    # Состояние индекса
    # =========================================================

    @property
    def is_ready(self) -> bool:
        return self._get_cached_index() is not None

    def _get_cached_index(
        self,
    ) -> Optional[tuple[list[dict], np.ndarray]]:
        return _get_cached_index(self.index_path)

    # =========================================================
    # Клиент GigaChat (для эмбеддинга запроса)
    # =========================================================

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            # Импорт внутри метода, а не на уровне модуля - чтобы
            # само наличие app.knowledge.vector_store в импортах не
            # требовало установленного gigachat SDK там, где
            # используется только LocalKnowledgeBase/keyword-режим
            # (например, KNOWLEDGE_BACKEND=keyword).
            from app.gigachat.client import GigaChatClient

            self._client = GigaChatClient(
                timeout=self.embedding_timeout,
                max_retries=0,
            )
        except Exception as exc:
            logger.warning(
                "Не удалось создать клиент GigaChat для "
                "эмбеддингов базы знаний: %s",
                exc,
            )
            return None

        return self._client

    # =========================================================
    # Эмбеддинг запроса
    # =========================================================

    def _embed_query(self, query: str) -> Optional[np.ndarray]:
        cache_key = " ".join(query.strip().lower().split())

        cached = self._query_cache.get(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()
        if client is None:
            return None

        started_at = time.monotonic()

        try:
            response = client.embeddings(
                [query],
                model=self.embedding_model,
            )
        except Exception as exc:
            logger.warning(
                "Embeddings API не ответил за %.0f мс, "
                "откат на поиск по ключевым словам: %s",
                (time.monotonic() - started_at) * 1000,
                exc,
            )
            return None

        data = getattr(response, "data", None)

        if not data:
            logger.warning(
                "Embeddings API вернул пустой ответ для запроса "
                "базы знаний."
            )
            return None

        vector = np.array(data[0].embedding, dtype=np.float32)
        vector = _normalize_vector(vector)

        self._query_cache.set(cache_key, vector)

        return vector

    # =========================================================
    # Поиск
    # =========================================================

    def search(self, query: str, limit: int = 5) -> list[dict]:

        if not query or not query.strip():
            return []

        index = self._get_cached_index()

        if index is None:
            return self._fallback.search(query, limit)

        chunks, vectors = index

        query_vector = self._embed_query(query)

        if query_vector is None:
            return self._fallback.search(query, limit)

        similarities = vectors @ query_vector

        # argpartition вместо полной сортировки - для типичного
        # размера базы знаний поддержки (сотни-тысячи чанков)
        # разница несущественна, но привычка не сортировать весь
        # массив ради top-k держится и на больших индексах.
        k = min(limit, len(similarities))
        top_indices = np.argpartition(-similarities, k - 1)[:k]
        top_indices = top_indices[
            np.argsort(-similarities[top_indices])
        ]

        results: list[dict] = []

        for idx in top_indices:
            score = float(similarities[idx])

            if score < self.min_score:
                break

            chunk = chunks[idx]

            results.append(
                {
                    "file": chunk["file"],
                    "score": score,
                    "content": chunk["text"],
                    "heading": chunk.get("heading", ""),
                }
            )

        if not results:
            # Семантически ничего похожего не нашлось - например,
            # запрос содержит точный код ошибки или редкий термин,
            # который эмбеддинг мог не "понять" достаточно
            # специфично. Поиск по ключевым словам подстраховывает
            # именно такие точные совпадения.
            return self._fallback.search(query, limit)

        return results
