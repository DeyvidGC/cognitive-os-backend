from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from cognitive_os.application.auth import authenticate
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import AuthToken, Membership, User

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
    return membership


Member = Annotated[Membership, Depends(current_membership)]


def capture_membership(member: Member) -> Membership:
    # Readers consume published knowledge, not the expert's raw capture sessions.
    if member.role not in {"owner", "author", "reviewer"}:
        raise ApplicationError(403, "Capture access denied")
    return member


CaptureMember = Annotated[Membership, Depends(capture_membership)]


def owner_membership(member: Member) -> Membership:
    # Technical/ops internals (job stage, attempts, indexing counters) are not
    # part of the client-facing surface any capture role should see.
    if member.role != "owner":
        raise ApplicationError(403, "Owner role required")
    return member


Owner = Annotated[Membership, Depends(owner_membership)]


def current_platform_staff(db: Db, token: Token) -> User:
    # Deliberately independent of X-Organization-ID and Membership: master mode
    # spans every organization, not the ones this user happens to belong to.
    user = db.get(User, token.user_id)
    if user is None or not user.is_platform_staff:
        raise ApplicationError(403, "Platform staff access required")
    return user


PlatformStaff = Annotated[User, Depends(current_platform_staff)]
