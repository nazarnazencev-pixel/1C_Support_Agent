import logging

from fastapi import HTTPException

from app.gigachat.errors import to_user_message


logger = logging.getLogger(__name__)


def send_message(manager, session_id: str, message: str) -> str:
    if not message.strip():
        raise HTTPException(400, "message не может быть пустым")
    try:
        session = manager.get_or_create(session_id)
        with session._lock:
            previous_request_id = session.last_request_id
            answer = session.ask(message)
            if session.last_request_failed:
                if session.db and session.last_request_id and session.last_request_id != previous_request_id:
                    try:
                        session.db.execute(
                            "UPDATE requests SET status = 'failed' WHERE id = ?",
                            (session.last_request_id,),
                        )
                        session.db.connection.commit()
                    except Exception:
                        logger.exception("Не удалось сохранить статус ошибки ответа")
                raise HTTPException(502, answer)
            return answer
    except HTTPException:
        raise
    except Exception as failure:
        logger.exception("Ошибка обработки сообщения")
        raise HTTPException(502, to_user_message(failure)) from failure
