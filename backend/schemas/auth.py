from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
