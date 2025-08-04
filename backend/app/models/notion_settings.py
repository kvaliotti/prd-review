from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class NotionSettings(Base):
    __tablename__ = "notion_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    notion_token = Column(Text, nullable=True)  # Encrypted Notion API token
    prd_database_id = Column(String(255), nullable=True)  # Notion database ID for PRDs
    research_database_id = Column(String(255), nullable=True)  # Notion database ID for User Research
    analytics_database_id = Column(String(255), nullable=True)  # Notion database ID for Data Analytics
    
    # Flags to control which databases to import
    import_prd = Column(Boolean, default=True)
    import_research = Column(Boolean, default=True)
    import_analytics = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notion_settings") 