import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import NotionSettings, NotionPage, NotionChunk, NotionComment, PageType
from app.services.notion_service import NotionService
from app.services.embedding_service import EmbeddingService
from app.crud.notion import get_user_notion_settings
from app.database.connection import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotionImportService:
    def __init__(self):
        self.logger = logger
        self.embedding_service = EmbeddingService()

    async def import_from_notion(
        self, 
        user_id: int, 
        force_update: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Import pages from Notion databases with streaming updates.
        Yields progress updates as the import proceeds.
        """
        async with get_db_context() as db:
            # Get user's Notion settings
            settings = get_user_notion_settings(db, user_id)
            if not settings or not settings.notion_token:
                yield {"error": "Notion settings not configured"}
                return

            notion_service = NotionService(settings.notion_token)
            
            # Test connection first
            if not await notion_service.test_connection():
                yield {"error": "Invalid Notion token or connection failed"}
                return

            databases = []
            if settings.import_prd and settings.prd_database_id:
                databases.append({"id": settings.prd_database_id, "type": PageType.prd})
            if settings.import_research and settings.research_database_id:
                databases.append({"id": settings.research_database_id, "type": PageType.research})
            if settings.import_analytics and settings.analytics_database_id:
                databases.append({"id": settings.analytics_database_id, "type": PageType.analytics})

            if not databases:
                yield {"status": "completed", "message": "No databases selected for import."}
                return

            yield {"status": "starting", "databases_count": len(databases)}

            total_pages_imported = 0
            total_chunks_created = 0
            total_embeddings_generated = 0

            for db_config in databases:
                database_id = db_config["id"]
                page_type = db_config["type"]
                
                yield {
                    "status": "fetching_pages",
                    "database_type": page_type.value,
                    "database_id": database_id
                }

                try:
                    # Fetch pages from database
                    notion_pages = await notion_service.get_database_pages(database_id, page_type)
                    
                    yield {
                        "status": "pages_fetched",
                        "database_type": page_type.value,
                        "pages_count": len(notion_pages)
                    }

                    # Process each page
                    for i, notion_page_data in enumerate(notion_pages):
                        try:
                            processed_data = await self._process_single_page(
                                db, notion_service, notion_page_data, page_type, user_id, force_update
                            )
                            
                            if processed_data:
                                total_pages_imported += 1
                                total_chunks_created += processed_data["chunks_count"]
                                total_embeddings_generated += processed_data["embeddings_count"]

                            yield {
                                "status": "page_processed",
                                "database_type": page_type.value,
                                "page_index": i + 1,
                                "total_pages": len(notion_pages),
                                "page_title": processed_data.get("title", "Unknown") if processed_data else "Skipped",
                                "chunks_created": processed_data.get("chunks_count", 0) if processed_data else 0,
                                "embeddings_created": processed_data.get("embeddings_count", 0) if processed_data else 0
                            }

                        except Exception as e:
                            self.logger.error(f"Error processing page: {e}")
                            yield {
                                "status": "page_error",
                                "database_type": page_type.value,
                                "page_index": i + 1,
                                "error": str(e)
                            }

                except Exception as e:
                    self.logger.error(f"Error fetching pages from database {database_id}: {e}")
                    yield {
                        "status": "database_error",
                        "database_type": page_type.value,
                        "error": str(e)
                    }

            yield {
                "status": "completed",
                "total_pages_imported": total_pages_imported,
                "total_chunks_created": total_chunks_created,
                "total_embeddings_generated": total_embeddings_generated
            }

    async def _process_single_page(
        self,
        db: Session,
        notion_service: NotionService,
        notion_page_data: Dict[str, Any],
        page_type: PageType,
        user_id: int,
        force_update: bool
    ) -> Optional[Dict[str, Any]]:
        """Process a single Notion page"""
        metadata = notion_service.extract_page_metadata(notion_page_data)
        notion_page_id = metadata["notion_page_id"]
        
        # Check if page already exists and if we should update it
        existing_page = db.query(NotionPage).filter(
            NotionPage.notion_page_id == notion_page_id
        ).first()
        
        if existing_page and not force_update:
            # Check if page was updated since last import
            last_edited_time = metadata.get("last_edited_time")
            if last_edited_time:
                last_edited_dt = datetime.fromisoformat(last_edited_time.replace('Z', '+00:00'))
                if last_edited_dt <= existing_page.updated_at:
                    self.logger.info(f"Page {notion_page_id} is up to date, skipping")
                    return None

        # Fetch page content
        content = await notion_service.get_page_content(notion_page_id)
        
        # Fetch comments
        comments_data = await notion_service.get_page_comments(notion_page_id)
        
        # Update or create page
        if existing_page:
            existing_page.title = metadata["title"]
            existing_page.content = content
            existing_page.page_type = page_type.value
            existing_page.notion_url = metadata["notion_url"]
            existing_page.parent_page_id = metadata["parent_page_id"]
            existing_page.last_edited_time = datetime.fromisoformat(
                metadata["last_edited_time"].replace('Z', '+00:00')
            ) if metadata.get("last_edited_time") else None
            
            # Delete existing chunks and comments to recreate them
            db.query(NotionChunk).filter(NotionChunk.page_id == existing_page.id).delete()
            db.query(NotionComment).filter(NotionComment.page_id == existing_page.id).delete()
            
            page = existing_page
        else:
            page = NotionPage(
                user_id=user_id,
                notion_page_id=notion_page_id,
                title=metadata["title"],
                content=content,
                page_type=page_type.value,
                notion_url=metadata["notion_url"],
                parent_page_id=metadata["parent_page_id"],
                last_edited_time=datetime.fromisoformat(
                    metadata["last_edited_time"].replace('Z', '+00:00')
                ) if metadata.get("last_edited_time") else None
            )
            db.add(page)
        
        db.flush()  # Get the page ID
        
        chunks_count = 0
        embeddings_count = 0
        
        # Process content into chunks and embeddings
        if content and content.strip():
            chunks = self.embedding_service.chunk_text(content)
            embedded_chunks = await self.embedding_service.embed_chunks(chunks)
            
            for i, chunk_data in enumerate(embedded_chunks):
                chunk = NotionChunk(
                    page_id=page.id,
                    chunk_index=i,
                    content=chunk_data["content"],
                    token_count=chunk_data["token_count"],
                    embedding=chunk_data["embedding"],
                    page_type=page_type  # Add page_type to chunk for PGVector filtering
                )
                db.add(chunk)
                chunks_count += 1
                if chunk_data["embedding"]:
                    embeddings_count += 1
        
        # Process comments
        for comment_data in comments_data:
            comment_content = self._extract_comment_content(comment_data)
            if comment_content:
                # Generate embedding for comment
                comment_embedding = await self.embedding_service.generate_embedding(comment_content)
                
                comment = NotionComment(
                    page_id=page.id,
                    notion_comment_id=comment_data["id"],
                    content=comment_content,
                    author=self._extract_comment_author(comment_data),
                    created_time=datetime.fromisoformat(
                        comment_data.get("created_time", "").replace('Z', '+00:00')
                    ) if comment_data.get("created_time") else None,
                    embedding=comment_embedding
                )
                db.add(comment)
                if comment_embedding:
                    embeddings_count += 1
        
        db.commit()
        
        return {
            "title": metadata["title"],
            "chunks_count": chunks_count,
            "embeddings_count": embeddings_count,
            "comments_count": len(comments_data)
        }

    def _extract_comment_content(self, comment_data: Dict[str, Any]) -> str:
        """Extract text content from a Notion comment"""
        rich_text = comment_data.get("rich_text", [])
        return "".join([text.get("plain_text", "") for text in rich_text])

    def _extract_comment_author(self, comment_data: Dict[str, Any]) -> Optional[str]:
        """Extract author information from a Notion comment"""
        created_by = comment_data.get("created_by", {})
        if created_by.get("type") == "person":
            person = created_by.get("person", {})
            return person.get("email") or created_by.get("name")
        return None

    async def get_import_status(self, user_id: int) -> Dict[str, Any]:
        """Get current import status for a user"""
        async with get_db_context() as db:
            pages = db.query(NotionPage).filter(NotionPage.user_id == user_id).all()
            
            if not pages:
                return {
                    "has_data": False,
                    "total_pages": 0,
                    "by_type": {}
                }
            
            by_type = {}
            for page_type in PageType:
                type_pages = [p for p in pages if p.page_type == page_type]
                by_type[page_type.value] = {
                    "pages": len(type_pages),
                    "last_updated": max([p.updated_at for p in type_pages]) if type_pages else None
                }
            
            return {
                "has_data": True,
                "total_pages": len(pages),
                "by_type": by_type,
                "last_import": max([p.updated_at for p in pages])
            } 