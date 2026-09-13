from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: Name
    organization_name: Name


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class MembershipResponse(BaseModel):
    organization_id: UUID
    organization_name: str
    role: Literal["owner", "author", "reviewer", "reader"]


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    memberships: list[MembershipResponse]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
