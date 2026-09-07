from pathlib import Path

from app.knowledge.base import LocalKnowledgeBase


def test_knowledge_search():
    kb = LocalKnowledgeBase("data/knowledge")
    results = kb.search("не проводится документ в 1С")
    assert isinstance(results, list)
    if results:
        assert "file" in results[0]
        assert "score" in results[0]
        assert "content" in results[0]


def test_knowledge_search_empty():
    kb = LocalKnowledgeBase("non_existent_folder")
    results = kb.search("тест")
    assert results == []


def test_knowledge_base_caches_unchanged_files(tmp_path, monkeypatch):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    doc = kb_dir / "doc.txt"
    doc.write_text(
        "ошибка при проведении документа",
        encoding="utf-8",
    )

    kb = LocalKnowledgeBase(str(kb_dir))

    original_read_text = Path.read_text
    calls = {"count": 0}

    def counting_read_text(self, *args, **kwargs):
        calls["count"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    # Два поиска подряд, файл не менялся - читаем с диска один раз.
    kb.search("ошибка")
    kb.search("документ")

    assert calls["count"] == 1


def test_knowledge_base_reloads_changed_file(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    doc = kb_dir / "doc.txt"
    doc.write_text("старый текст ошибка", encoding="utf-8")

    kb = LocalKnowledgeBase(str(kb_dir))

    first = kb.search("ошибка")
    assert first[0]["content"] == "старый текст ошибка"

    # Меняем mtime и содержимое - должно перечитаться.
    doc.write_text("новый текст ошибка", encoding="utf-8")

    second = kb.search("ошибка")
    assert second[0]["content"] == "новый текст ошибка"


def test_knowledge_base_matches_word_forms(tmp_path):
    """
    Раньше сравнивались только точные словоформы: документ со
    словом "ошибка" не находился по запросу "ошибки"/"ошибкой".
    """

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    doc = kb_dir / "doc.txt"
    doc.write_text(
        "При проведении документа возникает ошибка.",
        encoding="utf-8",
    )

    kb = LocalKnowledgeBase(str(kb_dir))

    for query in ("ошибки", "ошибкой", "ошибок"):
        results = kb.search(query)
        assert results, f"не нашлось для запроса: {query}"
        assert "ошибка" in results[0]["content"]


def test_knowledge_base_ignores_punctuation():
    kb = LocalKnowledgeBase("data/knowledge")

    with_punct = kb.search("документ, не проводится!")
    without_punct = kb.search("документ не проводится")

    assert with_punct
    assert [r["file"] for r in with_punct] == (
        [r["file"] for r in without_punct]
    )
