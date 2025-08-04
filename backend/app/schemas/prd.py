from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PRDBase(BaseModel):
    title: str
    content: Optional[str] = None


class PRDCreate(PRDBase):
    pass


class PRDUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class PRD(PRDBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 