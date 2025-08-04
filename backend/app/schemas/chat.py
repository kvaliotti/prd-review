from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class MessageBase(BaseModel):
    content: str
    role: str


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: int
    chat_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatBase(BaseModel):
    title: str


class ChatCreate(ChatBase):
    pass


class Chat(ChatBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[Message]] = []

    class Config:
        from_attributes = True


class ChatList(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    message: str 