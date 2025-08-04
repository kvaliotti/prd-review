from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import NotionSettings, NotionPage, NotionChunk, NotionComment, PageType
from app.core.config import RetrieverType


def get_user_notion_settings(db: Session, user_id: int) -> Optional[NotionSettings]:
    """Get user's Notion settings"""
    return db.query(NotionSettings).filter(NotionSettings.user_id == user_id).first()


def create_or_update_notion_settings(
    db: Session,
    user_id: int,
    notion_token: Optional[str] = None,
    prd_database_id: Optional[str] = None,
    research_database_id: Optional[str] = None,
    analytics_database_id: Optional[str] = None,
    import_prd: Optional[bool] = None,
    import_research: Optional[bool] = None,
    import_analytics: Optional[bool] = None,
    retriever_type: Optional[RetrieverType] = None
) -> NotionSettings:
    """Create or update user's Notion settings"""
    settings = get_user_notion_settings(db, user_id)
    
    if settings:
        # Update existing settings
        if notion_token is not None:
            settings.notion_token = notion_token
        if prd_database_id is not None:
            settings.prd_database_id = prd_database_id
        if research_database_id is not None:
            settings.research_database_id = research_database_id
        if analytics_database_id is not None:
            settings.analytics_database_id = analytics_database_id
        if import_prd is not None:
            settings.import_prd = import_prd
        if import_research is not None:
            settings.import_research = import_research
        if import_analytics is not None:
            settings.import_analytics = import_analytics
        if retriever_type is not None:
            settings.retriever_type = retriever_type.value
    else:
        # Create new settings
        settings = NotionSettings(
            user_id=user_id,
            notion_token=notion_token,
            prd_database_id=prd_database_id,
            research_database_id=research_database_id,
            analytics_database_id=analytics_database_id,
            import_prd=import_prd if import_prd is not None else True,
            import_research=import_research if import_research is not None else True,
            import_analytics=import_analytics if import_analytics is not None else True,
            retriever_type=retriever_type.value if retriever_type is not None else RetrieverType.NAIVE.value
        )
        db.add(settings)
    
    db.commit()
    db.refresh(settings)
    return settings


def get_user_pages(
    db: Session, 
    user_id: int, 
    page_type: Optional[PageType] = None,
    limit: int = 100,
    offset: int = 0
) -> List[NotionPage]:
    """Get user's Notion pages with optional filtering"""
    query = db.query(NotionPage).filter(NotionPage.user_id == user_id)
    
    if page_type:
        query = query.filter(NotionPage.page_type == page_type)
    
    return query.order_by(NotionPage.updated_at.desc()).offset(offset).limit(limit).all()


def get_page_by_id(db: Session, page_id: int, user_id: int) -> Optional[NotionPage]:
    """Get a specific page by ID for a user"""
    return db.query(NotionPage).filter(
        NotionPage.id == page_id,
        NotionPage.user_id == user_id
    ).first()


def get_page_chunks(db: Session, page_id: int) -> List[NotionChunk]:
    """Get all chunks for a page"""
    return db.query(NotionChunk).filter(
        NotionChunk.page_id == page_id
    ).order_by(NotionChunk.chunk_index).all()


def get_page_comments(db: Session, page_id: int) -> List[NotionComment]:
    """Get all comments for a page"""
    return db.query(NotionComment).filter(
        NotionComment.page_id == page_id
    ).order_by(NotionComment.created_time).all()


def create_page_from_file(db: Session, user_id: int, title: str, content: str, page_type: PageType) -> NotionPage:
    """Create a NotionPage from an uploaded file"""
    
    page = NotionPage(
        user_id=user_id,
        notion_page_id=f"file-{title}", # Create a unique ID
        title=title,
        content=content,
        page_type=page_type,
        notion_url=None, # No Notion URL for file uploads
    )
    
    db.add(page)
    db.commit()
    db.refresh(page)
    
    return page


def search_pages_by_title(
    db: Session, 
    user_id: int, 
    search_term: str,
    page_type: Optional[PageType] = None,
    limit: int = 50
) -> List[NotionPage]:
    """Search pages by title"""
    query = db.query(NotionPage).filter(
        NotionPage.user_id == user_id,
        NotionPage.title.ilike(f"%{search_term}%")
    )
    
    if page_type:
        query = query.filter(NotionPage.page_type == page_type)
    
    return query.order_by(NotionPage.updated_at.desc()).limit(limit).all()


def delete_user_notion_data(db: Session, user_id: int) -> bool:
    """Delete all Notion data for a user"""
    try:
        # Delete all pages (cascades to chunks and comments)
        deleted_pages = db.query(NotionPage).filter(NotionPage.user_id == user_id).delete()
        
        # Delete settings
        deleted_settings = db.query(NotionSettings).filter(NotionSettings.user_id == user_id).delete()
        
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def get_user_notion_stats(db: Session, user_id: int) -> dict:
    """Get statistics about user's Notion data"""
    pages = db.query(NotionPage).filter(NotionPage.user_id == user_id).all()
    
    if not pages:
        return {
            "total_pages": 0,
            "by_type": {},
            "total_chunks": 0,
            "total_comments": 0
        }
    
    stats = {
        "total_pages": len(pages),
        "by_type": {},
        "total_chunks": 0,
        "total_comments": 0
    }
    
    for page_type in PageType:
        type_pages = [p for p in pages if p.page_type == page_type]
        stats["by_type"][page_type.value] = len(type_pages)
    
    # Count chunks and comments
    for page in pages:
        chunk_count = db.query(NotionChunk).filter(NotionChunk.page_id == page.id).count()
        comment_count = db.query(NotionComment).filter(NotionComment.page_id == page.id).count()
        stats["total_chunks"] += chunk_count
        stats["total_comments"] += comment_count
    
    return stats 