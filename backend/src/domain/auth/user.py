from datetime import datetime
from pydantic import BaseModel


class User(BaseModel):
    id:              int | None = None
    email:           str
    username:        str
    hashed_password: str
    is_admin:        bool = False
    is_active:       bool = True
    created_at:      datetime | None = None

    model_config = {"frozen": True}
