import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from notion_client import Client
from notion_client.errors import APIResponseError
from app.models import NotionPage, NotionComment, PageType
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotionService:
    def __init__(self, notion_token: str):
        self.client = Client(auth=notion_token)
        self.logger = logger

    async def get_database_pages(self, database_id: str, page_type: PageType) -> List[Dict[str, Any]]:
        """Fetch all pages from a Notion database"""
        try:
            pages = []
            has_more = True
            start_cursor = None
            
            while has_more:
                query_payload = {"database_id": database_id}
                if start_cursor:
                    query_payload["start_cursor"] = start_cursor
                
                response = self.client.databases.query(**query_payload)
                pages.extend(response["results"])
                
                has_more = response["has_more"]
                start_cursor = response.get("next_cursor")
                
                # Add small delay to respect rate limits
                await asyncio.sleep(0.1)
            
            self.logger.info(f"Fetched {len(pages)} pages from database {database_id}")
            return pages
            
        except APIResponseError as e:
            self.logger.error(f"Error fetching pages from database {database_id}: {e}")
            raise

    async def get_page_content(self, page_id: str) -> str:
        """Fetch the full content of a Notion page"""
        try:
            blocks = await self._get_all_blocks(page_id)
            content = self._blocks_to_text(blocks)
            return content
            
        except APIResponseError as e:
            self.logger.error(f"Error fetching content for page {page_id}: {e}")
            raise

    async def _get_all_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        """Recursively fetch all blocks from a page or block"""
        blocks = []
        has_more = True
        start_cursor = None
        
        while has_more:
            query_payload = {"block_id": block_id}
            if start_cursor:
                query_payload["start_cursor"] = start_cursor
            
            response = self.client.blocks.children.list(**query_payload)
            current_blocks = response["results"]
            
            # Process each block and get children if they exist
            for block in current_blocks:
                blocks.append(block)
                
                # If block has children, recursively fetch them
                if block.get("has_children", False):
                    children = await self._get_all_blocks(block["id"])
                    blocks.extend(children)
            
            has_more = response["has_more"]
            start_cursor = response.get("next_cursor")
            
            # Add small delay to respect rate limits
            await asyncio.sleep(0.1)
        
        return blocks

    def _blocks_to_text(self, blocks: List[Dict[str, Any]]) -> str:
        """Convert Notion blocks to plain text"""
        text_parts = []
        
        for block in blocks:
            block_type = block["type"]
            
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                rich_text = block[block_type].get("rich_text", [])
                text = "".join([t["plain_text"] for t in rich_text])
                if text.strip():
                    text_parts.append(text.strip())
            
            elif block_type == "code":
                rich_text = block[block_type].get("rich_text", [])
                code_text = "".join([t["plain_text"] for t in rich_text])
                if code_text.strip():
                    text_parts.append(f"```\n{code_text.strip()}\n```")
            
            elif block_type == "quote":
                rich_text = block[block_type].get("rich_text", [])
                quote_text = "".join([t["plain_text"] for t in rich_text])
                if quote_text.strip():
                    text_parts.append(f"> {quote_text.strip()}")
            
            elif block_type == "callout":
                rich_text = block[block_type].get("rich_text", [])
                callout_text = "".join([t["plain_text"] for t in rich_text])
                if callout_text.strip():
                    text_parts.append(f"💡 {callout_text.strip()}")
        
        return "\n\n".join(text_parts)

    async def get_page_comments(self, page_id: str) -> List[Dict[str, Any]]:
        """Fetch all comments for a page"""
        try:
            comments = []
            has_more = True
            start_cursor = None
            
            while has_more:
                query_payload = {"block_id": page_id}
                if start_cursor:
                    query_payload["start_cursor"] = start_cursor
                
                response = self.client.comments.list(**query_payload)
                comments.extend(response["results"])
                
                has_more = response["has_more"]
                start_cursor = response.get("next_cursor")
                
                # Add small delay to respect rate limits
                await asyncio.sleep(0.1)
            
            self.logger.info(f"Fetched {len(comments)} comments for page {page_id}")
            return comments
            
        except APIResponseError as e:
            self.logger.error(f"Error fetching comments for page {page_id}: {e}")
            return []  # Comments are optional, so return empty list on error

    def extract_page_metadata(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from a Notion page"""
        properties = page_data.get("properties", {})
        
        # Try to get title from various possible property names
        title = "Untitled"
        for prop_name, prop_data in properties.items():
            if prop_data.get("type") == "title" and prop_data.get("title"):
                title = "".join([t["plain_text"] for t in prop_data["title"]])
                break
        
        return {
            "notion_page_id": page_data["id"],
            "title": title,
            "notion_url": page_data["url"],
            "last_edited_time": page_data.get("last_edited_time"),
            "parent_page_id": self._get_parent_page_id(page_data)
        }

    def _get_parent_page_id(self, page_data: Dict[str, Any]) -> Optional[str]:
        """Extract parent page ID if the page is a subpage"""
        parent = page_data.get("parent", {})
        if parent.get("type") == "page_id":
            return parent.get("page_id")
        return None

    async def test_connection(self) -> bool:
        """Test if the Notion token is valid"""
        try:
            self.client.users.me()
            return True
        except APIResponseError:
            return False 