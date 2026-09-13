from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from cognitive_os.api.dependencies import Db, Token
from cognitive_os.application import auth
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, request: Request, response: Response, db: Db):
    if not request.app.state.settings.registration_enabled:
        raise ApplicationError(403, "Registration is disabled")
    response.headers["Cache-Control"] = "no-store"
    return auth.register(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, response: Response, db: Db):
    response.headers["Cache-Control"] = "no-store"
    return auth.login(db, str(data.email), data.password.get_secret_value(),
                      request.app.state.settings.token_ttl_seconds)


@router.get("/me", response_model=UserResponse)
def me(db: Db, token: Token, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return auth.profile(db, token.user_id)


@router.post("/logout", status_code=204)
def logout(db: Db, token: Token):
    token.revoked_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)
