from typing import Any, Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "xianyu-backend"
    time: str
    version: str = "1.0.0"
