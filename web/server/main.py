import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.chat_server import app, session_manager, ChatRequest, ChatResponse, post_message
from app.admin.panel import AdminPanel
from app.config.settings import KNOWLEDGE_BACKEND, KNOWLEDGE_PATH
from server.knowledge import ArticleInput, KnowledgeRepository
from server.security import require_admin
from server.uploads import analyze_upload
from server.chat import send_message
from server.streaming import stream_response
from server.tls import configure_gigachat_certificates
from support_agent_db.database import Database


configure_gigachat_certificates()
app.router.routes = [route for route in app.router.routes if getattr(route, "endpoint", None) is not post_message]
knowledge = KnowledgeRepository(Path(KNOWLEDGE_PATH), KNOWLEDGE_BACKEND == "keyword")
admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


def get_panel():
    database = Database()
    try:
        yield AdminPanel(database)
    finally:
        database.close()


@app.middleware("http")
async def validate_request(request: Request, call_next):
    content_length = request.headers.get("content-length", "0")
    try:
        if int(content_length) > 41 * 1024 * 1024:
            return JSONResponse({"detail": "Запрос слишком большой."}, status_code=413)
    except ValueError:
        return JSONResponse({"detail": "Некорректная длина запроса."}, status_code=400)
    if request.url.path.startswith("/api/chat/"):
        session_id = request.url.path.split("/")[3]
        if not re.fullmatch(r"[a-zA-Z0-9_-]{8,100}", session_id):
            return JSONResponse({"detail": "Некорректный идентификатор диалога."}, status_code=400)
        if request.method == "POST" and request.url.path.rstrip("/") == f"/api/chat/{session_id}":
            try:
                payload = await request.json()
            except ValueError:
                return JSONResponse({"detail": "Некорректный JSON."}, status_code=400)
            if not isinstance(payload, dict) or not isinstance(payload.get("message"), str) or len(payload["message"]) > 12000:
                return JSONResponse({"detail": "Сообщение должно содержать не более 12000 символов."}, status_code=422)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "knowledge_editable": knowledge.editable}


@app.post("/api/chat/{session_id}", response_model=ChatResponse)
def chat_message(session_id: str, request: ChatRequest, http_request: Request):
    if 'text/event-stream' in http_request.headers.get('accept', ''):
        return stream_response(lambda: send_message(session_manager, session_id, request.message))
    return ChatResponse(answer=send_message(session_manager, session_id, request.message))


@app.get("/api/knowledge")
def list_knowledge():
    return knowledge.list_articles()


@app.post("/api/chat/{session_id}/file")
def upload_attachment(session_id: str, http_request: Request, file: UploadFile, message: str = Form(...)):
    if 'text/event-stream' in http_request.headers.get('accept', ''):
        return stream_response(lambda: analyze_upload(session_manager, session_id, message, file), file.file.close)
    try:
        return {"answer": analyze_upload(session_manager, session_id, message, file)}
    finally:
        file.file.close()


@admin_router.get("/dashboard")
def dashboard(panel: AdminPanel = Depends(get_panel)):
    return panel.get_dashboard_summary()


@admin_router.get("/daily-stats")
def daily_stats(panel: AdminPanel = Depends(get_panel)):
    return panel.get_daily_stats()


@admin_router.get("/category-stats")
def category_stats(panel: AdminPanel = Depends(get_panel)):
    return panel.get_category_stats()


@admin_router.get("/escalations")
def escalations(panel: AdminPanel = Depends(get_panel)):
    return panel.get_open_escalations()


@admin_router.post("/knowledge")
def save_knowledge(article: ArticleInput):
    try:
        return knowledge.save(article)
    except OSError as failure:
        raise HTTPException(503, "Не удалось сохранить файл базы знаний.") from failure


app.include_router(admin_router)
