from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, validator

Direction = Literal["buy", "sell", "long", "short"]

class TradeSignal(BaseModel):
    symbol: str = Field(..., min_length=1)
    direction: Direction
    price: float = Field(..., gt=0)
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    stop_loss: float = Field(..., gt=0)
    take_profit_1: float = Field(..., gt=0)
    take_profit_2: float = Field(..., gt=0)
    take_profit_3: float = Field(..., gt=0)

    @validator("timestamp")
    def normalize_ts(cls, v):
        if v > 10**12:
            v /= 1000
        if v <= 0:
            raise ValueError("timestamp must be positive")
        return v
