"""API 依赖：鉴权。"""
from __future__ import annotations

from fastapi import Header, HTTPException, Query, status

from app.core.security import is_token_valid


def require_auth(authorization: str = Header(default=None), token: str = Query(default=None)):
    """简单 Bearer token 鉴权（未开启登录时跳过）。

    支持两种携带方式：
    1. Authorization: Bearer <token> 头（fetch 请求）
    2. ?token=<token> 查询参数（浏览器直接下载 / 图片预览，无法自定义头）
    """
    from app.core.config import settings

    if not settings.use_auth:
        return True

    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization[len("Bearer "):].strip()
    elif token:
        auth_token = token

    if not auth_token or not is_token_valid(auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或 token 无效"
        )
    return True
