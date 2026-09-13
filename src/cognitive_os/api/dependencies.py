from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from cognitive_os.application.auth import authenticate
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import AuthToken, Membership

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    engine = request.app.state.engine
    if engine is None:
        raise ApplicationError(503, "Database is not configured")
    with Session(engine, expire_on_commit=False) as db:
        yield db


Db = Annotated[Session, Depends(get_db)]


def current_token(db: Db, credentials: Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer)
]) -> AuthToken:
    if credentials is None:
        raise ApplicationError(401, "Authentication required")
    return authenticate(db, credentials.credentials)


Token = Annotated[AuthToken, Depends(current_token)]


def current_membership(db: Db, token: Token,
                       x_organization_id: Annotated[UUID, Header()]) -> Membership:
    membership = db.get(Membership, (x_organization_id, token.user_id))
    if membership is None:
        raise ApplicationError(403, "Organization access denied")
    # Readers consume published knowledge, not the expert's raw capture sessions.
    if membership.role not in {"owner", "author", "reviewer"}:
        raise ApplicationError(403, "Capture access denied")
    return membership


Member = Annotated[Membership, Depends(current_membership)]
