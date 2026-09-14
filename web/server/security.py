import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials


basic_auth = HTTPBasic(auto_error=False)


def require_admin(credentials: HTTPBasicCredentials | None = Depends(basic_auth)) -> None:
    expected_user = os.environ.get("WEB_ADMIN_USER", "admin")
    expected_password = os.environ.get("WEB_ADMIN_PASSWORD", "")
    if len(expected_password) < 12:
        raise HTTPException(503, "Администратор сервера ещё не настроил доступ.")
    supplied_user = credentials.username if credentials else ""
    supplied_password = credentials.password if credentials else ""
    valid_user = secrets.compare_digest(supplied_user.encode("utf-8"), expected_user.encode("utf-8"))
    valid_password = secrets.compare_digest(supplied_password.encode("utf-8"), expected_password.encode("utf-8"))
    if not valid_user or not valid_password:
        raise HTTPException(401, "Неверный логин или пароль.")
