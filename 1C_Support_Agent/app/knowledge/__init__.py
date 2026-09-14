from app.knowledge.base import KnowledgeBase, LocalKnowledgeBase
from app.knowledge.vector_store import VectorKnowledgeBase


def create_knowledge_base() -> KnowledgeBase:
    """
    Фабрика базы знаний для SupportAgent.

    Выбор реализации управляется настройкой KNOWLEDGE_BACKEND
    (см. app/config/settings.py):

        "vector"  (по умолчанию) - VectorKnowledgeBase, поиск по
                  смысловой близости с автоматическим откатом на
                  поиск по ключевым словам, если векторный индекс
                  недоступен;
        "keyword" - LocalKnowledgeBase напрямую, без обращения к
                  Embeddings API вообще. Полезно как аварийный
                  выключатель, если Embeddings API недоступен/
                  отключён для организации, без изменения кода.

    Вынесено в отдельную функцию (а не создание объекта напрямую в
    SupportAgent.__init__), чтобы способ выбора реализации был в
    одном месте и легко тестировался/переопределялся.
    """

    from app.config.settings import (
        GIGACHAT_EMBEDDING_MODEL,
        KNOWLEDGE_BACKEND,
        KNOWLEDGE_EMBEDDING_TIMEOUT,
        KNOWLEDGE_INDEX_PATH,
        KNOWLEDGE_MIN_SCORE,
        KNOWLEDGE_PATH,
    )

    if KNOWLEDGE_BACKEND == "keyword":
        return LocalKnowledgeBase(KNOWLEDGE_PATH)

    return VectorKnowledgeBase(
        knowledge_path=KNOWLEDGE_PATH,
        index_path=KNOWLEDGE_INDEX_PATH,
        embedding_model=GIGACHAT_EMBEDDING_MODEL,
        embedding_timeout=KNOWLEDGE_EMBEDDING_TIMEOUT,
        min_score=KNOWLEDGE_MIN_SCORE,
    )


__all__ = [
    "KnowledgeBase",
    "LocalKnowledgeBase",
    "VectorKnowledgeBase",
    "create_knowledge_base",
]
