from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.database.connection import Base


class PageType(enum.Enum):
    prd = "prd"
    research = "research"
    analytics = "analytics"


class NotionPage(Base):
    __tablename__ = "notion_pages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notion_page_id = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)  # Full page content
    page_type = Column(Enum(PageType), nullable=False)
    notion_url = Column(String(1000), nullable=True)
    parent_page_id = Column(String(255), nullable=True)  # For subpages
    last_edited_time = Column(DateTime(timezone=True), nullable=True)  # From Notion API
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    chunks = relationship("NotionChunk", back_populates="page", cascade="all, delete-orphan")
    comments = relationship("NotionComment", back_populates="page", cascade="all, delete-orphan") 