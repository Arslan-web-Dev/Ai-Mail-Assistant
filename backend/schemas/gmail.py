from typing import Literal

from pydantic import BaseModel

ConnectionStatus = Literal["connected", "disconnected", "connecting", "error"]


class GmailAuthUrlResponse(BaseModel):
    authorization_url: str


class GmailStatusResponse(BaseModel):
    status: ConnectionStatus
    gmail_email: str | None = None
    connected_at: str | None = None
    last_error: str | None = None


class GmailDisconnectResponse(BaseModel):
    status: ConnectionStatus
