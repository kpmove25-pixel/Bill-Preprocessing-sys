"""认证路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.security import issue_token, verify_credentials
from app.schemas.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if not verify_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = issue_token()
    return TokenResponse(token=token, auth_enabled=settings.use_auth)
