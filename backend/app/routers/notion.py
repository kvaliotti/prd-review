from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import asyncio

from app.database.connection import get_db
from app.models import User, PageType
from app.core.security import verify_token
from app.crud import user as user_crud
from app.schemas.notion import (
    NotionSettings, NotionSettingsUpdate, NotionPage, NotionPageWithDetails,
    ImportStatusResponse, ImportProgressUpdate, KnowledgeBaseStats,
    PageSearchRequest, PageSearchResponse
)
from app.crud import notion as notion_crud
from app.services.notion_import_service import NotionImportService
from app.services.notion_service import NotionService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/notion", tags=["notion"])
notion_import_service = NotionImportService()

# Authentication setup for router
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        email = verify_token(credentials.credentials, credentials_exception)
        user = user_crud.get_user_by_email(db, email=email)
        if user is None:
            raise credentials_exception
        return user
    except Exception:
        raise credentials_exception


@router.get("/settings", response_model=Optional[NotionSettings])
async def get_notion_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's Notion settings"""
    settings = notion_crud.get_user_notion_settings(db, current_user.id)
    if settings:
        # Don't expose the actual token in the response
        settings_dict = {
            "id": settings.id,
            "user_id": settings.user_id,
            "notion_token": "***" if settings.notion_token else None,
            "prd_database_id": settings.prd_database_id,
            "research_database_id": settings.research_database_id,
            "analytics_database_id": settings.analytics_database_id,
            "import_prd": settings.import_prd,
            "import_research": settings.import_research,
            "import_analytics": settings.import_analytics,
            "retriever_type": settings.retriever_type,
            "created_at": settings.created_at,
            "updated_at": settings.updated_at
        }
        return settings_dict
    return None


@router.post("/settings", response_model=NotionSettings)
async def update_notion_settings(
    settings_update: NotionSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's Notion settings"""
    try:
        # Test the connection if a token is provided
        if settings_update.notion_token:
            notion_service = NotionService(settings_update.notion_token)
            if not await notion_service.test_connection():
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Notion token - could not connect to Notion API"
                )
        
        # Update settings
        settings = notion_crud.create_or_update_notion_settings(
            db=db,
            user_id=current_user.id,
            notion_token=settings_update.notion_token,
            prd_database_id=settings_update.prd_database_id,
            research_database_id=settings_update.research_database_id,
            analytics_database_id=settings_update.analytics_database_id,
            import_prd=settings_update.import_prd,
            import_research=settings_update.import_research,
            import_analytics=settings_update.import_analytics,
            retriever_type=settings_update.retriever_type
        )
        
        # Don't expose the actual token in the response
        settings_dict = {
            "id": settings.id,
            "user_id": settings.user_id,
            "notion_token": "***" if settings.notion_token else None,
            "prd_database_id": settings.prd_database_id,
            "research_database_id": settings.research_database_id,
            "analytics_database_id": settings.analytics_database_id,
            "import_prd": settings.import_prd,
            "import_research": settings.import_research,
            "import_analytics": settings.import_analytics,
            "retriever_type": settings.retriever_type,
            "created_at": settings.created_at,
            "updated_at": settings.updated_at
        }
        
        logger.info("Notion settings updated", user_id=current_user.id)
        return settings_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating Notion settings", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to update Notion settings"
        )


@router.post("/test-connection")
async def test_notion_connection(
    payload: Optional[NotionSettingsUpdate] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test Notion API connection with provided token or saved token"""
    token_to_test = None

    if payload and payload.notion_token:
        token_to_test = payload.notion_token
    else:
        settings = notion_crud.get_user_notion_settings(db, current_user.id)
        if settings and settings.notion_token:
            token_to_test = settings.notion_token

    if not token_to_test:
        raise HTTPException(
            status_code=400,
            detail="Notion token not provided and no token is configured"
        )
    
    try:
        notion_service = NotionService(token_to_test)
        is_connected = await notion_service.test_connection()
        
        return {
            "connected": is_connected,
            "message": "Connection successful" if is_connected else "Connection failed"
        }
    except Exception as e:
        logger.error("Error testing Notion connection", user_id=current_user.id, error=str(e))
        return {
            "connected": False,
            "message": f"Connection error: {str(e)}"
        }


@router.post("/import")
async def start_notion_import(
    force_update: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Start importing from Notion with streaming progress updates"""
    
    async def generate_import_stream():
        try:
            async for update in notion_import_service.import_from_notion(
                user_id=current_user.id,
                force_update=force_update
            ):
                # Send progress update as SSE
                yield f"data: {json.dumps(update)}\n\n"
                
                # Add small delay to prevent overwhelming the client
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error("Error during Notion import", user_id=current_user.id, error=str(e))
            error_update = {
                "status": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_update)}\n\n"
    
    return StreamingResponse(
        generate_import_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/import-status", response_model=ImportStatusResponse)
async def get_import_status(
    current_user: User = Depends(get_current_user)
):
    """Get current import status"""
    try:
        status = await notion_import_service.get_import_status(current_user.id)
        return status
    except Exception as e:
        logger.error("Error getting import status", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get import status"
        )


@router.get("/pages", response_model=List[NotionPage])
async def get_notion_pages(
    page_type: Optional[str] = Query(None, alias="page_type"),
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's Notion pages"""
    
    validated_page_type: Optional[PageType] = None
    if page_type:
        try:
            validated_page_type = PageType[page_type.lower()]
        except KeyError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid page type: '{page_type}'. Valid types are: {[pt.value for pt in PageType]}"
            )
            
    try:
        pages = notion_crud.get_user_pages(
            db=db,
            user_id=current_user.id,
            page_type=validated_page_type,
            limit=limit,
            offset=offset
        )
        return pages
    except Exception as e:
        logger.error("Error getting Notion pages", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get pages"
        )


@router.get("/pages/{page_id}", response_model=NotionPageWithDetails)
async def get_notion_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific Notion page with chunks and comments"""
    try:
        page = notion_crud.get_page_by_id(db, page_id, current_user.id)
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        
        chunks = notion_crud.get_page_chunks(db, page_id)
        comments = notion_crud.get_page_comments(db, page_id)
        
        return {
            **page.__dict__,
            "chunks": chunks,
            "comments": comments
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting Notion page", user_id=current_user.id, page_id=page_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get page"
        )

@router.post("/upload-file")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    page_type: PageType = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a knowledge base file (PDF, Markdown)"""
    
    content = await file.read()
    
    # Here you would add logic to parse PDF/MD and extract text
    # For now, we'll just use the raw content for simplicity
    
    try:
        page = notion_crud.create_page_from_file(
            db=db,
            user_id=current_user.id,
            title=file.filename,
            content=content.decode('utf-8'),
            page_type=page_type,
        )
        
        # Optionally, trigger embedding here or have a background job
        
        return {"filename": file.filename, "page_id": page.id}
    except Exception as e:
        logger.error(f"Failed to upload and process file {file.filename}", error=str(e))
        raise HTTPException(status_code=500, detail="File upload failed")

@router.post("/pages/search", response_model=PageSearchResponse)
async def search_notion_pages(
    search_request: PageSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search Notion pages by title"""
    
    validated_page_type: Optional[PageType] = None
    if search_request.page_type:
        try:
            validated_page_type = PageType[search_request.page_type.upper()]
        except KeyError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid page type: '{search_request.page_type}'. Valid types are: {[pt.name for pt in PageType]}"
            )

    try:
        pages = notion_crud.search_pages_by_title(
            db=db,
            user_id=current_user.id,
            search_term=search_request.search_term,
            page_type=validated_page_type,
            limit=search_request.limit
        )
        
        return {
            "pages": pages,
            "total_found": len(pages)
        }
    except Exception as e:
        logger.error("Error searching Notion pages", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to search pages"
        )


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get knowledge base statistics"""
    try:
        stats = notion_crud.get_user_notion_stats(db, current_user.id)
        return stats
    except Exception as e:
        logger.error("Error getting knowledge base stats", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get statistics"
        )


@router.delete("/data")
async def delete_notion_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all Notion data for the user"""
    try:
        success = notion_crud.delete_user_notion_data(db, current_user.id)
        if success:
            logger.info("Notion data deleted", user_id=current_user.id)
            return {"message": "All Notion data deleted successfully"}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete Notion data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting Notion data", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to delete data"
        ) 