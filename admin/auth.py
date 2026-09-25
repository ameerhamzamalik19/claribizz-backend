import os
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "fallback-secret-change-this")
COOKIE_NAME = "claribizz_admin_session"
COOKIE_MAX_AGE = 60 * 60 * 8  # 8 hours

serializer = URLSafeTimedSerializer(ADMIN_SECRET_KEY)


def create_session_token(username: str) -> str:
    return serializer.dumps(username, salt="admin-session")


def verify_session_token(token: str) -> str | None:
    try:
        username = serializer.loads(token, salt="admin-session", max_age=COOKIE_MAX_AGE)
        return username
    except (BadSignature, SignatureExpired):
        return None


def check_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def get_current_admin(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def require_admin(request: Request) -> RedirectResponse | None:
    """Call this at the top of every protected route."""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    return None