import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import (
    AuthToken, LocalCredential, Membership, Organization, User,
)
from cognitive_os.schemas.auth import RegisterRequest, TokenResponse, UserResponse

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash(secrets.token_urlsafe(32))


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register(db: Session, data: RegisterRequest) -> UserResponse:
    user = User(identity_subject=f"local:{uuid4()}", display_name=data.display_name)
    organization = Organization(name=data.organization_name)
    db.add_all([user, organization])
    try:
        db.flush()
        db.add(LocalCredential(user_id=user.id, email=str(data.email).lower(),
                               password_hash=password_hash.hash(data.password.get_secret_value())))
        db.add(Membership(organization_id=organization.id, user_id=user.id, role="owner"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApplicationError(409, "Account could not be registered") from exc
    return profile(db, user.id)


def login(db: Session, email: str, password: str, ttl: int) -> TokenResponse:
    credential = db.scalar(select(LocalCredential).where(
        LocalCredential.email == email.lower()).with_for_update())
    now = datetime.now(UTC)
    valid, updated_hash = password_hash.verify_and_update(
        password, credential.password_hash if credential else dummy_hash)
    if credential is None:
        raise ApplicationError(401, "Invalid credentials")
    if credential.locked_until and credential.locked_until > now:
        raise ApplicationError(401, "Invalid credentials")
    if not valid:
        if credential.locked_until:
            credential.failed_attempts = 0
            credential.locked_until = None
        credential.failed_attempts += 1
        if credential.failed_attempts >= 5:
            credential.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise ApplicationError(401, "Invalid credentials")
    credential.failed_attempts = 0
    credential.locked_until = None
    if updated_hash:
        credential.password_hash = updated_hash
    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(seconds=ttl)
    db.add(AuthToken(token_hash=digest_token(raw_token), user_id=credential.user_id,
                     expires_at=expires_at))
    db.commit()
    return TokenResponse(access_token=raw_token, expires_at=expires_at)


def authenticate(db: Session, token: str) -> AuthToken:
    if len(token) > 256:
        raise ApplicationError(401, "Invalid or expired token")
    stored = db.get(AuthToken, digest_token(token))
    if stored is None or stored.revoked_at or stored.expires_at <= datetime.now(UTC):
        raise ApplicationError(401, "Invalid or expired token")
    return stored


def profile(db: Session, user_id) -> UserResponse:
    user = db.get(User, user_id)
    credential = db.get(LocalCredential, user_id)
    if user is None or credential is None:
        raise ApplicationError(401, "Account unavailable")
    memberships = db.execute(select(Membership, Organization.name).join(
        Organization, Organization.id == Membership.organization_id
    ).where(Membership.user_id == user_id)).all()
    return UserResponse(id=user.id, email=credential.email, display_name=user.display_name,
                        memberships=[dict(organization_id=m.organization_id,
                                          organization_name=name, role=m.role)
                                     for m, name in memberships])
