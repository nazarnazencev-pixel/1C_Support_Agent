import hashlib
import hmac
import os
import secrets
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config.settings import validate_config, WEB_RESPONSE_BUDGET_MS
from app.gigachat.errors import to_user_message
from app.session.session_manager import SessionManager
from support_agent_db.database import Database

BASE = Path(__file__).resolve().parent.parent
WEB = BASE / "web"
UPLOADS = BASE / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin1")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "11111")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "wizard-lizard-admin-secret")
COOKIE = "wizard_admin"

manager = SessionManager()
app = FastAPI(title="Wizard_Lizard")
app.mount("/static", StaticFiles(directory=WEB), name="static")


class ChatRequest(BaseModel):
    message: str


class LoginRequest(BaseModel):
    login: str
    password: str


def _token() -> str:
    nonce = secrets.token_hex(16)
    sig = hmac.new(ADMIN_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def _admin_ok(request: Request) -> bool:
    token = request.cookies.get(COOKIE, "")
    if "." not in token:
        return False
    nonce, sig = token.split(".", 1)
    expected = hmac.new(ADMIN_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _require_admin(request: Request):
    if not _admin_ok(request):
        raise HTTPException(status_code=401, detail="Требуется вход администратора")


@app.on_event("startup")
def startup():
    validate_config()
    manager.start_background_cleanup()
    Database().initialize()


@app.on_event("shutdown")
def shutdown():
    manager.shutdown()


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
def admin():
    return (WEB / "admin.html").read_text(encoding="utf-8")


@app.post("/api/chat/{session_id}/greeting")
def greeting(session_id: str):
    try:
        return {"answer": manager.get_greeting(session_id)}
    except Exception as exc:
        raise HTTPException(502, to_user_message(exc))


@app.post("/api/chat/{session_id}")
def chat(session_id: str, request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(400, "message не может быть пустым")
    try:
        # GigaChatClient ограничивает один сетевой вызов 3.8 с,
        # оставляя запас до 5 с на БД/HTTP. Повторные попытки отключены.
        answer = manager.ask(session_id, request.message, channel="web")
        return {"answer": answer, "target_ms": WEB_RESPONSE_BUDGET_MS}
    except Exception as exc:
        raise HTTPException(502, to_user_message(exc))


@app.post("/api/chat/{session_id}/specialist")
def specialist(session_id: str):
    session = manager.get_or_create(session_id)
    escalation_id = session.request_specialist()
    if escalation_id is None:
        raise HTTPException(400, "Сначала отправьте сообщение в чат")
    return {"ok": True, "escalation_id": escalation_id,
            "message": "Запрос специалисту отправлен. Оператор увидит его в админ-панели."}


@app.post("/api/chat/{session_id}/file")
def file_upload(session_id: str, file: UploadFile = File(...), message: str = Form(...)):
    suffix = Path(file.filename or "").suffix.lower()
    allowed = {".pdf", ".docx", ".txt", ".xlsx", ".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed:
        raise HTTPException(400, "Этот тип файла не поддерживается")
    target = UPLOADS / f"{secrets.token_hex(8)}{suffix}"
    with target.open("wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)
    session = manager.get_or_create(session_id)
    try:
        answer = manager.analyze_file(session_id, str(target), message)
        return {"answer": answer}
    except Exception as exc:
        raise HTTPException(502, to_user_message(exc))


@app.post("/api/admin/login")
def admin_login(data: LoginRequest, response: Response):
    if hmac.compare_digest(data.login, ADMIN_LOGIN) and hmac.compare_digest(data.password, ADMIN_PASSWORD):
        response.set_cookie(COOKIE, _token(), httponly=True, samesite="lax", max_age=8 * 3600)
        return {"ok": True}
    raise HTTPException(401, "Неверный логин или пароль")


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/admin/me")
def admin_me(request: Request):
    _require_admin(request)
    return {"ok": True}


@app.get("/api/admin/summary")
def admin_summary(request: Request):
    _require_admin(request)
    return AdminData().summary()


@app.get("/api/admin/daily")
def admin_daily(request: Request):
    _require_admin(request)
    return AdminData().daily()


@app.get("/api/admin/requests")
def admin_requests(request: Request):
    _require_admin(request)
    return AdminData().requests()


@app.get("/api/admin/escalations")
def admin_escalations(request: Request):
    _require_admin(request)
    return AdminData().escalations()


class AdminData:
    def __init__(self):
        self.db = Database()
        self.db.initialize()

    def summary(self):
        data = self.db.dashboard_summary()
        data["attachments_count"] = self.db.attachment_count()
        data["specialist_calls"] = self.db.specialist_call_count()
        return data

    def daily(self):
        return self.db.daily_stats()

    def requests(self):
        return self.db.recent_requests(50)

    def escalations(self):
        return self.db.open_escalations()
