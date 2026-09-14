import re

from pathlib import Path


# Буквы (кириллица + латиница) - пунктуация, цифры и прочее
# автоматически не попадают в токены.
_WORD_RE = re.compile(r"[a-zа-яё]+")

# Минимальная длина слова, чтобы учитываться при поиске.
_MIN_WORD_LENGTH = 3

# Длина "псевдо-основы" слова. Полное посимвольное совпадение
# слов не учитывает морфологию: "ошибка"/"ошибки"/"ошибкой" не
# совпадали бы друг с другом. Обрезка до первых N букв - грубый,
# но не требующий внешних библиотек способ находить однокоренные
# словоформы для большинства русских слов, у которых окончание
# короче корня.
_STEM_LENGTH = 4


def _stems(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())

    return {
        word[:_STEM_LENGTH] if len(word) > _STEM_LENGTH else word
        for word in words
        if len(word) >= _MIN_WORD_LENGTH
    }


class KnowledgeBase:
    """
    Базовый интерфейс базы знаний.

    В дальнейшем здесь можно будет заменить локальный поиск
    на векторную БД, не меняя остальной код агента.
    """

    def search(self, query: str, limit: int = 5) -> list[dict]:
        raise NotImplementedError


class LocalKnowledgeBase(KnowledgeBase):
    """
    Простая локальная база знаний.

    Ищет текстовые совпадения в файлах:
    .txt
    .md
    """

    def __init__(self, knowledge_path: str = "data/knowledge"):
        self.knowledge_path = Path(knowledge_path)

        # Кэш: путь -> (mtime, текст, набор псевдо-основ слов
        # текста). Позволяет не перечитывать и не токенизировать
        # заново файлы, которые не изменились с прошлого вызова.
        # Раньше search() читал ВСЕ файлы базы знаний заново на
        # каждое сообщение пользователя - блокирующий I/O в
        # синхронном коде на каждый запрос, без всякого кэша.
        self._cache: dict[str, tuple[float, str, set[str]]] = {}

    def _load_documents(
        self,
    ) -> dict[str, tuple[str, set[str]]]:
        """
        Возвращает {путь: (текст, набор псевдо-основ)} по всем
        .txt/.md файлам базы знаний, читая и токенизируя с диска
        только новые или изменившиеся файлы.
        """

        if not self.knowledge_path.exists():
            return {}

        documents: dict[str, tuple[str, set[str]]] = {}

        for file_path in self.knowledge_path.rglob("*"):
            if file_path.suffix.lower() not in {".txt", ".md"}:
                continue

            key = str(file_path)

            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                continue

            cached = self._cache.get(key)

            if cached is not None and cached[0] == mtime:
                documents[key] = (cached[1], cached[2])
                continue

            try:
                text = file_path.read_text(
                    encoding="utf-8"
                )
            except (OSError, UnicodeDecodeError):
                continue

            stems = _stems(text)

            self._cache[key] = (mtime, text, stems)
            documents[key] = (text, stems)

        # Удаляем из кэша файлы, которых больше нет на диске.
        for stale_key in set(self._cache) - set(documents):
            self._cache.pop(stale_key, None)

        return documents

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query_stems = _stems(query)

        if not query_stems:
            return []

        results = []

        for file_path, (text, stems) in (
            self._load_documents().items()
        ):

            score = len(query_stems & stems)

            if score == 0:
                continue

            results.append(
                {
                    "file": file_path,
                    "score": score,
                    "content": text,
                }
            )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return results[:limit]