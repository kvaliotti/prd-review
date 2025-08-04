from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.models import PageType


class NotionSettingsBase(BaseModel):
    notion_token: Optional[str] = None
    prd_database_id: Optional[str] = None
    research_database_id: Optional[str] = None
    analytics_database_id: Optional[str] = None
    import_prd: Optional[bool] = None
    import_research: Optional[bool] = None
    import_analytics: Optional[bool] = None


class NotionSettingsCreate(NotionSettingsBase):
    pass


class NotionSettingsUpdate(NotionSettingsBase):
    pass


class NotionSettings(NotionSettingsBase):
    id: int
    user_id: int
    import_prd: bool
    import_research: bool
    import_analytics: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotionPageBase(BaseModel):
    title: str
    content: Optional[str] = None
    page_type: PageType
    notion_url: Optional[str] = None
    parent_page_id: Optional[str] = None
    last_edited_time: Optional[datetime] = None


class NotionPageCreate(NotionPageBase):
    notion_page_id: str
    user_id: int


class NotionPage(NotionPageBase):
    id: int
    notion_page_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotionChunkBase(BaseModel):
    chunk_index: int
    content: str
    token_count: Optional[int] = None


class NotionChunk(NotionChunkBase):
    id: int
    page_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class NotionCommentBase(BaseModel):
    content: str
    author: Optional[str] = None
    created_time: Optional[datetime] = None


class NotionComment(NotionCommentBase):
    id: int
    page_id: int
    notion_comment_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class NotionPageWithDetails(NotionPage):
    chunks: List[NotionChunk] = []
    comments: List[NotionComment] = []


class ImportStatusResponse(BaseModel):
    has_data: bool
    total_pages: int
    by_type: Dict[str, Any]
    last_import: Optional[datetime] = None


class ImportProgressUpdate(BaseModel):
    status: str
    message: Optional[str] = None
    database_type: Optional[str] = None
    database_id: Optional[str] = None
    page_index: Optional[int] = None
    total_pages: Optional[int] = None
    page_title: Optional[str] = None
    chunks_created: Optional[int] = None
    embeddings_created: Optional[int] = None
    error: Optional[str] = None
    total_pages_imported: Optional[int] = None
    total_chunks_created: Optional[int] = None
    total_embeddings_generated: Optional[int] = None


class KnowledgeBaseStats(BaseModel):
    total_pages: int
    by_type: Dict[str, int]
    total_chunks: int
    total_comments: int


class PageSearchRequest(BaseModel):
    search_term: str
    page_type: Optional[PageType] = None
    limit: int = Field(default=50, le=100)


class PageSearchResponse(BaseModel):
    pages: List[NotionPage]
    total_found: int 