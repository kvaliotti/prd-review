import asyncio
import tiktoken
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-3-small"
        self.max_tokens = 8192  # Max tokens for text-embedding-3-small
        self.chunk_overlap = 200  # Overlap between chunks in tokens
        self.logger = logger
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            self.logger.error(f"Failed to initialize tokenizer: {e}")
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text"""
        if not self.tokenizer:
            # Fallback estimation: roughly 4 chars per token
            return len(text) // 4
        
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            self.logger.error(f"Error counting tokens: {e}")
            return len(text) // 4

    def chunk_text(self, text: str, chunk_size: int = 6000) -> List[Dict[str, Any]]:
        """
        Split text into chunks suitable for embedding.
        Returns list of dictionaries with 'content' and 'token_count'.
        """
        if not text or not text.strip():
            return []

        # If text is smaller than chunk size, return as single chunk
        token_count = self.count_tokens(text)
        if token_count <= chunk_size:
            return [{
                "content": text.strip(),
                "token_count": token_count
            }]

        chunks = []
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        current_chunk = ""
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            paragraph_tokens = self.count_tokens(paragraph)
            
            # If single paragraph is too large, split it further
            if paragraph_tokens > chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "token_count": current_tokens
                    })
                    current_chunk = ""
                    current_tokens = 0
                
                # Split large paragraph by sentences
                sub_chunks = self._split_large_paragraph(paragraph, chunk_size)
                chunks.extend(sub_chunks)
                continue
            
            # Check if adding this paragraph would exceed chunk size
            if current_tokens + paragraph_tokens > chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append({
                    "content": current_chunk.strip(),
                    "token_count": current_tokens
                })
                current_chunk = paragraph
                current_tokens = paragraph_tokens
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                    current_tokens += paragraph_tokens + self.count_tokens("\n\n")
                else:
                    current_chunk = paragraph
                    current_tokens = paragraph_tokens
        
        # Add final chunk if it has content
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "token_count": current_tokens
            })
        
        self.logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def _split_large_paragraph(self, paragraph: str, chunk_size: int) -> List[Dict[str, Any]]:
        """Split a large paragraph by sentences"""
        import re
        
        # Split by sentences (basic sentence boundary detection)
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_tokens = self.count_tokens(sentence)
            
            # If single sentence is still too large, split by words
            if sentence_tokens > chunk_size:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "token_count": current_tokens
                    })
                    current_chunk = ""
                    current_tokens = 0
                
                word_chunks = self._split_by_words(sentence, chunk_size)
                chunks.extend(word_chunks)
                continue
            
            if current_tokens + sentence_tokens > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "token_count": current_tokens
                })
                current_chunk = sentence
                current_tokens = sentence_tokens
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                    current_tokens += sentence_tokens + 1  # +1 for space
                else:
                    current_chunk = sentence
                    current_tokens = sentence_tokens
        
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "token_count": current_tokens
            })
        
        return chunks

    def _split_by_words(self, text: str, chunk_size: int) -> List[Dict[str, Any]]:
        """Split text by words as last resort"""
        words = text.split()
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for word in words:
            word_tokens = self.count_tokens(word)
            
            if current_tokens + word_tokens > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "token_count": current_tokens
                })
                current_chunk = word
                current_tokens = word_tokens
            else:
                if current_chunk:
                    current_chunk += " " + word
                    current_tokens += word_tokens + 1
                else:
                    current_chunk = word
                    current_tokens = word_tokens
        
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "token_count": current_tokens
            })
        
        return chunks

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            self.logger.debug(f"Generated embedding for text of {len(text)} characters")
            return embedding
            
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            raise

    async def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Generate embeddings for multiple texts in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                
                self.logger.info(f"Generated embeddings for batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error generating embeddings for batch starting at {i}: {e}")
                # Add empty embeddings for failed batch
                embeddings.extend([[] for _ in batch])
        
        return embeddings

    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add embeddings to chunks"""
        if not chunks:
            return []
        
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await self.generate_embeddings_batch(texts)
        
        embedded_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            embedded_chunks.append({
                **chunk,
                "embedding": embedding
            })
        
        return embedded_chunks 