from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id:        int
    email:     str
    username:  str
    is_admin:  bool
    is_active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}
