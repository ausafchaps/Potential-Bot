from datetime import datetime

from pydantic import BaseModel


class AIUsageWindow(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: datetime


class AIUsageResponse(BaseModel):
    enabled: bool
    minute: AIUsageWindow
    day: AIUsageWindow
