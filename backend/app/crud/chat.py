from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.chat import Chat
from app.models.message import Message
from app.schemas.chat import ChatCreate, MessageCreate
from typing import List, Optional


def create_chat(db: Session, chat: ChatCreate, user_id: int) -> Chat:
    """Create a new chat"""
    db_chat = Chat(
        user_id=user_id,
        title=chat.title
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat


def get_user_chats(db: Session, user_id: int) -> List[Chat]:
    """Get all chats for a user with message count"""
    return (
        db.query(
            Chat.id,
            Chat.title,
            Chat.created_at,
            Chat.updated_at,
            func.count(Message.id).label("message_count")
        )
        .outerjoin(Message)
        .filter(Chat.user_id == user_id)
        .group_by(Chat.id)
        .order_by(Chat.updated_at.desc())
        .all()
    )


def get_chat_by_id(db: Session, chat_id: int, user_id: int) -> Optional[Chat]:
    """Get chat by ID for specific user"""
    return (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == user_id)
        .first()
    )


def get_chat_messages(db: Session, chat_id: int, user_id: int) -> List[Message]:
    """Get all messages for a chat"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        return []
    
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def create_message(db: Session, message: MessageCreate, chat_id: int) -> Message:
    """Create a new message"""
    db_message = Message(
        chat_id=chat_id,
        role=message.role,
        content=message.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Update chat timestamp
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        chat.updated_at = func.now()
        db.commit()
    
    return db_message


def update_chat_title(db: Session, chat_id: int, user_id: int, title: str) -> Optional[Chat]:
    """Update chat title"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if chat:
        chat.title = title
        db.commit()
        db.refresh(chat)
    return chat 