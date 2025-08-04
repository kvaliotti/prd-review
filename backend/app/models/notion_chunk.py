from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from app.database.connection import Base
from app.models.notion_page import PageType


class NotionChunk(Base):
    __tablename__ = "notion_chunks"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("notion_pages.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order within the page
    content = Column(Text, nullable=False)  # Chunked content for embedding
    token_count = Column(Integer, nullable=True)  # Number of tokens in this chunk
    embedding = Column(ARRAY(Float), nullable=True)  # Vector embedding (1536 dimensions for text-embedding-3-small)
    page_type = Column(Enum(PageType), nullable=True)  # Denormalized from notion_pages for PGVector filtering
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    page = relationship("NotionPage", back_populates="chunks")


class NotionComment(Base):
    __tablename__ = "notion_comments"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("notion_pages.id", ondelete="CASCADE"), nullable=False)
    notion_comment_id = Column(String(255), nullable=False, unique=True, index=True)
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=True)
    created_time = Column(DateTime(timezone=True), nullable=True)  # From Notion API
    embedding = Column(ARRAY(Float), nullable=True)  # Vector embedding for comment
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    page = relationship("NotionPage", back_populates="comments") 