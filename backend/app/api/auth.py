from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import COOKIE_NAME, create_access_token, get_current_teacher, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    settings = get_settings()

    if payload.username != settings.teacher_username or not verify_password(
        payload.password, settings.teacher_password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    token = create_access_token(subject=payload.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment != "development",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return LoginResponse(username=payload.username)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=LoginResponse)
def me(username: str = Depends(get_current_teacher)) -> LoginResponse:
    return LoginResponse(username=username)
