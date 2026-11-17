from pydantic import BaseModel, Field
from typing import Literal
class ReceiverInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
class FaultInput(BaseModel):
    fault: Literal['none', 'lose_receipt', 'tamper', 'unavailable']
class OutboundPlanInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    job_id: int
    receiver_id: int
    interval_seconds: int = Field(default=86400, ge=60, le=2592000)
    delay_seconds: int = Field(default=0, ge=0, le=2592000)
