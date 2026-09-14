"""
HTTP API для чата поддержки 1С.

До этого файла SessionManager.ask() вызывался только в тестах:
main.py работал напрямую с голым SupportAgent (в обход Session,
SessionManager и Database), а app/admin/web.py только читал БД для
дашборда оператора. Ни один код не принимал сообщение из реального
канала (сайт, Bitrix24 и т.п.) и не прогонял его через
SessionManager -> Session -> SupportAgent + Database.

Этот модуль - минимальная, но реально работающая точка входа для
такого канала.

Запуск:

    uvicorn app.api.chat_server:app --reload

Эндпоинты:

    POST /api/chat/{session_id}/greeting
        Приветствие агента для новой сессии.

    POST /api/chat/{session_id}
        {"message": "..."} -> {"answer": "..."}

    POST /api/chat/{session_id}/feedback
        {"rating": 0..10, "comment": "..."}
"""

import logging

from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
)

from pydantic import BaseModel

from app.config.settings import (
    validate_config,
)

from app.gigachat.errors import (
    to_user_message,
)

from app.session.session_manager import (
    SessionManager,
)


logger = logging.getLogger(__name__)


# Один процесс - один SessionManager. Как и раньше указано в
# документации SessionManager, для нескольких процессов/инстансов
# нужен внешний общий backend (RedisSessionManager, БД) - это
# отдельная задача, здесь не решается.
session_manager = SessionManager()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Явная проверка конфигурации при старте сервиса - без неё
    # сервис поднимался бы и без GIGACHAT_CREDENTIALS, а ошибка
    # проявлялась бы только на первом реальном сообщении.
    validate_config()

    session_manager.start_background_cleanup()
    yield
    session_manager.shutdown()


app = FastAPI(
    title="1C Support AI - Chat API",
    lifespan=_lifespan,
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str


class FeedbackRequest(BaseModel):
    rating: int
    comment: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: int | None


@app.post(
    "/api/chat/{session_id}/greeting",
    response_model=ChatResponse,
)
def get_greeting(session_id: str) -> ChatResponse:
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=400,
            detail="session_id не может быть пустым",
        )

    try:
        answer = session_manager.get_greeting(session_id)
    except Exception as exc:
        logger.exception(
            "Ошибка при получении приветствия (session_id=%s)",
            session_id,
        )
        raise HTTPException(
            status_code=502,
            detail=to_user_message(exc),
        ) from exc

    return ChatResponse(answer=answer)


@app.post(
    "/api/chat/{session_id}",
    response_model=ChatResponse,
)
def post_message(
    session_id: str,
    request: ChatRequest,
) -> ChatResponse:
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=400,
            detail="session_id не может быть пустым",
        )

    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="message не может быть пустым",
        )

    try:
        answer = session_manager.ask(
            session_id,
            request.message,
        )
    except Exception as exc:
        logger.exception(
            "Ошибка при обработке сообщения (session_id=%s)",
            session_id,
        )
        raise HTTPException(
            status_code=502,
            detail=to_user_message(exc),
        ) from exc

    return ChatResponse(answer=answer)


@app.post(
    "/api/chat/{session_id}/feedback",
    response_model=FeedbackResponse,
)
def post_feedback(
    session_id: str,
    request: FeedbackRequest,
) -> FeedbackResponse:
    session = session_manager.get(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Сессия не найдена",
        )

    try:
        feedback_id = session.submit_csat_feedback(
            rating=request.rating,
            comment=request.comment,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Ошибка при сохранении обратной связи (session_id=%s)",
            session_id,
        )
        raise HTTPException(
            status_code=502,
            detail=to_user_message(exc),
        ) from exc

    return FeedbackResponse(feedback_id=feedback_id)
