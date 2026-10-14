"""简单登录与令牌管理（MVP：内存令牌，重启失效）。"""
import hmac
import secrets
import time

from app.core.config import settings

# token -> 过期时间戳
_TOKEN_STORE: dict = {}
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12 小时


def verify_credentials(username: str, password: str) -> bool:
    if not settings.use_auth:
        return True
    ok_user = hmac.compare_digest(username, settings.app_username)
    ok_pass = hmac.compare_digest(password, settings.app_password)
    return ok_user and ok_pass


def issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _TOKEN_STORE[token] = time.time() + TOKEN_TTL_SECONDS
    return token


def is_token_valid(token: str) -> bool:
    if not settings.use_auth:
        return True
    expiry = _TOKEN_STORE.get(token)
    if expiry is None:
        return False
    if time.time() > expiry:
        _TOKEN_STORE.pop(token, None)
        return False
    return True


def revoke_token(token: str) -> None:
    _TOKEN_STORE.pop(token, None)
