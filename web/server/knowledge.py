import base64
import hashlib
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field


CATEGORIES = {"1c_errors", "1c_documents", "1c_integrations", "faq", "custom", "general"}


class ArticleInput(BaseModel):
    id: str | None = None
    revision: str | None = None
    title: str = Field(min_length=1, max_length=160, pattern=r"^[^\r\n]+$")
    category: str = Field(max_length=80)
    content: str = Field(min_length=1, max_length=500000)


class KnowledgeRepository:
    def __init__(self, root: Path, editable: bool):
        self.root = root.resolve()
        self.editable = editable
        self.lock = threading.Lock()

    def describe(self, path: Path) -> dict:
        content = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(self.root)
        heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return {
            "id": base64.urlsafe_b64encode(relative.as_posix().encode("utf-8")).decode("ascii").rstrip("="),
            "title": heading.group(1).strip() if heading else path.stem.replace("_", " "),
            "category": relative.parts[0] if len(relative.parts) > 1 else "general",
            "content": content,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "revision": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def list_articles(self) -> list[dict]:
        with self.lock:
            articles = []
            for path in sorted(self.root.rglob("*")):
                if path.suffix.lower() not in {".md", ".txt"} or not path.is_file():
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                    continue
                if path.stat().st_size > 1024 * 1024:
                    continue
                try:
                    articles.append(self.describe(path))
                except (OSError, UnicodeDecodeError):
                    continue
            return articles

    def resolve_identifier(self, identifier: str) -> Path:
        try:
            relative = base64.b64decode(identifier + "=" * (-len(identifier) % 4), altchars=b"-_", validate=True).decode("utf-8")
            path = (self.root / relative).resolve()
        except (ValueError, UnicodeDecodeError, OSError) as failure:
            raise HTTPException(400, "Некорректный идентификатор материала.") from failure
        if not path.is_relative_to(self.root) or path.suffix.lower() not in {".md", ".txt"}:
            raise HTTPException(400, "Недопустимый путь материала.")
        return path

    def save(self, article: ArticleInput) -> dict:
        if not self.editable:
            raise HTTPException(409, "Редактирование доступно в режиме KNOWLEDGE_BACKEND=keyword. Векторный индекс обновляется администратором сервера.")
        if article.category not in CATEGORIES or not article.title.strip() or not article.content.strip():
            raise HTTPException(422, "Укажите название, категорию и текст материала.")
        with self.lock:
            if article.id:
                target = self.resolve_identifier(article.id)
                if not target.is_file():
                    raise HTTPException(404, "Материал не найден.")
                current = self.describe(target)
                if current["revision"] != article.revision:
                    raise HTTPException(409, "Материал изменён другим пользователем. Откройте его заново перед редактированием.")
                if current["category"] != article.category:
                    raise HTTPException(422, "Категорию существующего материала изменить нельзя.")
            else:
                target = self.root / article.category / f"{uuid.uuid4().hex}.md"
                if not target.resolve().is_relative_to(self.root):
                    raise HTTPException(400, "Недопустимый путь материала.")
            target.parent.mkdir(parents=True, exist_ok=True)
            body = re.sub(r"\A\s*#\s+[^\n]*\n?", "", article.content).strip()
            content = f"# {article.title.strip()}\n\n{body}\n"
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False) as temporary:
                    temporary.write(content)
                    temporary_path = Path(temporary.name)
                os.replace(temporary_path, target)
            finally:
                if temporary_path and temporary_path.exists():
                    temporary_path.unlink()
            return self.describe(target)
