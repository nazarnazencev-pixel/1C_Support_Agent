from pathlib import Path


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

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not self.knowledge_path.exists():
            return []

        query_words = {
            word.lower()
            for word in query.split()
            if len(word) >= 3
        }

        if not query_words:
            return []

        results = []

        for file_path in self.knowledge_path.rglob("*"):
            if file_path.suffix.lower() not in {".txt", ".md"}:
                continue

            try:
                text = file_path.read_text(
                    encoding="utf-8"
                )
            except (OSError, UnicodeDecodeError):
                continue

            text_lower = text.lower()

            score = sum(
                1
                for word in query_words
                if word in text_lower
            )

            if score == 0:
                continue

            results.append(
                {
                    "file": str(file_path),
                    "score": score,
                    "content": text,
                }
            )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return results[:limit]