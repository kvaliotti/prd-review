from typing import Annotated, List, TypedDict, Literal, Any, Optional, Dict
from pydantic import BaseModel, Field
import operator
import os
import asyncio
from enum import Enum
from dataclasses import dataclass, fields
from sqlalchemy.orm import Session
from sqlalchemy import text

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.retrievers import BaseRetriever

from langgraph.constants import Send
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command

# Tavily web search imports
from tavily import TavilyClient, AsyncTavilyClient

# Contextual compression retriever imports
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

from app.database.connection import get_db
from app.core.config import settings, RetrieverType


class Query(BaseModel):
    search_query: str = Field(description="Query for RAG retrieval to get relevant context")


class Queries(BaseModel):
    queries: List[Query] = Field(description="List of queries for RAG retrieval")


class WebQuery(BaseModel):
    search_query: str = Field(description="Query for web search to get market insights and validation")


class WebQueries(BaseModel):
    queries: List[WebQuery] = Field(description="List of queries for web search")


class MarketSuggestionsSection(BaseModel):
    """Structured output for feature and design suggestions based on web search."""
    feature_ideas: List[str] = Field(description="List of specific feature ideas and functionality suggestions based on web research (4-6 bullet points with source citations)")
    ux_ui_suggestions: List[str] = Field(description="List of UX/UI patterns, design ideas, and behavioral solutions from similar products (4-6 bullet points with source citations)")
    sources: List[str] = Field(description="List of web sources used in this analysis", default_factory=list)


class AnalysisSection(BaseModel):
    """Structured output for each PRD analysis section."""
    analysis: str = Field(description="Detailed analysis of this PRD section (200-300 words) in bullet list format. MUST include direct citations from provided research context using format '[Source: Document Name]' when referencing insights from retrieved documents.")
    recommendations: List[str] = Field(description="List of specific improvement recommendations (3-5 bullet points). Include source citations when recommendations are based on retrieved research.")
    potential_pitfalls: List[str] = Field(description="List of potential issues, unclear phrases, unsupported claims, logical gaps, or research contradictions (2-4 bullet points).")
    supported_points: List[str] = Field(description="List of clearly supported points, ideas, or thoughts that are well-backed by research evidence (2-4 bullet points with source citations).")
    score: int = Field(description="Score from 0-5 (0=worst, 5=best)", ge=0, le=5)
    sources: List[str] = Field(description="List of document sources used in this analysis", default_factory=list)


class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview of the main topics and concepts to be covered in this section.")
    analysis: str = Field(default="", description="Analysis of the PRD section.")
    recommendations: List[str] = Field(default_factory=list, description="List of improvement recommendations.")
    potential_pitfalls: List[str] = Field(default_factory=list, description="List of potential issues, unclear phrases, unsupported claims, logical gaps, or research contradictions.")
    supported_points: List[str] = Field(default_factory=list, description="List of clearly supported points, ideas, or thoughts that are well-backed by research evidence.")
    score: int = Field(default=0, description="Score for this section from 0 to 5.")
    sources: List[str] = Field(default_factory=list, description="Sources used for this section analysis.")


class SectionState(TypedDict):
    prd_content: str
    prd_title: str 
    section: Section
    search_queries: List[Query]
    source_str: str
    sources_used: List[str]
    retrieval_logs: List[str]
    search_iterations: int


class SectionOutputState(TypedDict):
    completed_sections: List[Section]
    retrieval_logs: List[str]


class MarketSuggestionsState(TypedDict):
    prd_content: str
    prd_title: str
    sections: List[Section]
    completed_sections: Annotated[List[Section], operator.add]
    retrieval_logs: Annotated[List[str], operator.add]
    web_search_logs: Annotated[List[str], operator.add]
    market_suggestions: Optional[dict]
    final_report: str
    web_queries: List[WebQuery]
    web_search_results: str


class ReportState(TypedDict):
    prd_content: str
    prd_title: str
    sections: List[Section]
    completed_sections: Annotated[List[Section], operator.add]
    retrieval_logs: Annotated[List[str], operator.add]
    web_search_logs: Annotated[List[str], operator.add]
    market_suggestions: Optional[dict]
    final_report: str


class ReportStateInput(TypedDict):
    prd_content: str
    prd_title: str


class ReportStateOutput(TypedDict):
    final_report: str
    sections: List[Section]


class Configuration(BaseModel):
    """Configuration for the PRD analysis pipeline."""
    
    writer_model: str = Field(default="gpt-4.1", description="OpenAI model for analysis")
    top_k: int = Field(default=5, description="Number of documents to retrieve from RAG")
    number_of_queries: int = Field(default=2, description="Number of RAG queries per section")
    retriever_type: RetrieverType = Field(default=RetrieverType.NAIVE, description="Type of retriever to use")

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "Configuration":
        configurable = config.get("configurable", {})
        return cls(**configurable)


def create_notion_retriever(db: Session, top_k: int = 5, retriever_type: RetrieverType = RetrieverType.NAIVE) -> BaseRetriever:
    """Create a LangChain PGVector retriever for research and analytics documents with optional contextual compression."""
    
    # Use the original database URL from settings (which has correct credentials)
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        # Convert to postgresql+psycopg format for langchain-postgres
        connection_string = db_url.replace("postgresql://", "postgresql+psycopg://")
    else:
        connection_string = db_url
    
    # Initialize embeddings (same as used for storing)
    embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
    
    try:
        try:
            print(f"🔗 Connecting to PGVector store...")
            
            # Create vector store - if tables exist, that's fine
            vectorstore = PGVector(
                embeddings=embeddings,
                connection=connection_string,
                collection_name="prd_research_docs",  # Unique collection for our research docs
                use_jsonb=True,
                pre_delete_collection=False,  # Don't delete existing collection
            )
            print(f"✅ Connected to PGVector store successfully")
            
        except Exception as e:
            # Handle the specific case where LangChain tables/types already exist
            error_str = str(e)
            if "duplicate key" in error_str and "langchain_pg_collection" in error_str:
                print(f"⚠️ LangChain tables already exist - using fallback retriever approach...")
                # Skip to fallback mechanism
                raise e
            else:
                print(f"❌ Unexpected PGVector error: {e}")
                raise e
        
        # Check if we need to populate the LangChain vector store
        _populate_langchain_vectorstore(db, vectorstore)
        
        # Create base retriever - filter not needed since vectorstore only contains research/analytics docs
        base_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k}
        )
        
        # Apply contextual compression if requested
        print(f"🔍 Checking retriever type: {retriever_type}")
        print(f"🔍 Is CONTEXTUAL_COMPRESSION? {retriever_type == RetrieverType.CONTEXTUAL_COMPRESSION}")
        
        if retriever_type == RetrieverType.CONTEXTUAL_COMPRESSION:
            print(f"🔑 Cohere API key available: {settings.cohere_api_key is not None}")
            if settings.cohere_api_key:
                try:
                    print(f"🔧 Creating Cohere compressor...")
                    compressor = CohereRerank(
                        model="rerank-v3.5",
                        cohere_api_key=settings.cohere_api_key
                    )
                    print(f"✅ Cohere compressor created successfully")
                    
                    print(f"🔧 Creating contextual compression retriever...")
                    retriever = ContextualCompressionRetriever(
                        base_compressor=compressor,
                        base_retriever=base_retriever
                    )
                    print(f"✅ Contextual compression retriever created successfully")
                    print(f"🔧 Created contextual compression retriever with Cohere rerank for research/analytics chunks")
                    return retriever
                except Exception as e:
                    print(f"⚠️ Failed to create contextual compression retriever: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"🔧 Falling back to naive retriever")
                    return base_retriever
            else:
                print(f"⚠️ Cohere API key not configured, falling back to naive retriever")
                return base_retriever
        else:
            print(f"🔧 Created naive PGVector retriever for research/analytics chunks")
            return base_retriever
            
    except Exception as e:
        print(f"❌ Error creating PGVector retriever: {e}")
        # Fallback to basic similarity search without filters
        vectorstore = PGVector(
            embeddings=embeddings,
            connection=connection_string,
            collection_name="prd_research_docs_fallback",
            use_jsonb=True,
        )
        
        fallback_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k}
        )
        
        # Apply contextual compression to fallback if requested
        if retriever_type == RetrieverType.CONTEXTUAL_COMPRESSION and settings.cohere_api_key:
            try:
                compressor = CohereRerank(
                    model="rerank-v3.5",
                    cohere_api_key=settings.cohere_api_key
                )
                return ContextualCompressionRetriever(
                    base_compressor=compressor,
                    base_retriever=fallback_retriever
                )
            except Exception as e:
                print(f"⚠️ Failed to create contextual compression for fallback: {e}")
                return fallback_retriever
        
        return fallback_retriever


def _populate_langchain_vectorstore(db: Session, vectorstore: PGVector):
    """Populate LangChain vectorstore with our research and analytics documents if empty."""
    from app.models.notion_chunk import NotionChunk
    from app.models.notion_page import NotionPage, PageType
    
    # Check if vectorstore already has documents
    try:
        # Try a simple similarity search to see if there are documents
        test_results = vectorstore.similarity_search("test", k=1)
        if test_results:
            print(f"✅ LangChain vectorstore already populated with {len(test_results)} documents")
            return
    except:
        pass  # Vectorstore is empty or has issues
    
    print("📦 Populating LangChain vectorstore with research and analytics documents...")
    
    # Get research and analytics chunks from our database
    chunks_with_pages = (
        db.query(NotionChunk, NotionPage)
        .join(NotionPage, NotionChunk.page_id == NotionPage.id)
        .filter(NotionPage.page_type.in_([PageType.research, PageType.analytics]))
        .filter(NotionChunk.embedding.isnot(None))
        .all()
    )
    
    print(f"📊 Found {len(chunks_with_pages)} chunks to migrate to LangChain vectorstore")
    
    if not chunks_with_pages:
        print("⚠️ No research/analytics chunks found to populate vectorstore")
        return
    
    # Convert to LangChain documents
    documents = []
    for chunk, page in chunks_with_pages:
        doc = Document(
            page_content=chunk.content,
            metadata={
                "source": page.title,
                "page_type": page.page_type.value,
                "notion_page_id": page.notion_page_id,
                "chunk_id": chunk.id
            }
        )
        documents.append(doc)
    
    # Add documents to vectorstore in batches
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        try:
            vectorstore.add_documents(batch)
            print(f"✅ Added batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
        except Exception as e:
            print(f"❌ Error adding batch {i//batch_size + 1}: {e}")
    
    print(f"🎯 Successfully populated LangChain vectorstore with {len(documents)} documents")


def deduplicate_and_format_sources(search_response, max_tokens_per_source=500, include_raw_content=True):
    """
    Takes a list of search responses and formats them into a readable string.
    Limits the raw_content to approximately max_tokens_per_source.
 
    Args:
        search_response: List of search response dicts, each containing:
            - query: str
            - results: List of dicts with fields:
                - title: str
                - url: str
                - content: str
                - score: float
                - raw_content: str|None
        max_tokens_per_source: int
        include_raw_content: bool
            
    Returns:
        str: Formatted string with deduplicated sources
    """
    # Collect all results
    sources_list = []
    for response in search_response:
        sources_list.extend(response['results'])
    
    # Deduplicate by URL
    unique_sources = {source['url']: source for source in sources_list}

    # Format output
    formatted_text = "Web Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"Source {source['title']}:\n===\n"
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += f"Most relevant content from source: {source['content']}\n===\n"
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = ''
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
                
    return formatted_text.strip()


async def tavily_search_async(search_queries):
    """
    Performs concurrent web searches using the Tavily API.

    Args:
        search_queries (List[WebQuery]): List of search queries to process

    Returns:
        List[dict]: List of search responses from Tavily API, one per query. Each response has format:
            {
                'query': str, # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': list,
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the webpage
                        'url': str,              # URL of the result
                        'content': str,          # Summary/snippet of content
                        'score': float,          # Relevance score
                        'raw_content': str|None  # Full page content if available
                    },
                    ...
                ]
            }
    """
    # Initialize async Tavily client
    tavily_async_client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    
    search_tasks = []
    for query in search_queries:
        search_tasks.append(
            tavily_async_client.search(
                query.search_query,
                max_results=5,
                include_raw_content=True,
                topic="general"
            )
        )

    # Execute all searches concurrently
    search_docs = await asyncio.gather(*search_tasks)

    return search_docs


# Section-specific analysis instructions
SECTION_INSTRUCTIONS = {
    "Audience": """You are an expert in PRD writing and analysis. 
Your task is to analyze the provided PRD and provide a detailed analysis of the audience section.

<PRD Content>
{prd_content}
</PRD Content>

<Retrieved Research Context>
{context}
</Retrieved Research Context>

Analyze the audience section by:
1. Evaluating insights about the audience and whether they are used consistently throughout the PRD
2. Assessing whether the product vision is built for this specific audience
3. Identifying any contradictions between audience insights and other PRD sections
4. Comparing with research data to validate audience assumptions

CRITICAL FORMATTING: 
- Provide your analysis in clear BULLET POINTS format
- When referencing insights from Retrieved Research Context, you MUST include direct citations using format [Source: Document Name]
- Structure your response to include: analysis (bullet points), recommendations (bullet points), potential_pitfalls (bullet points), and supported_points (bullet points)

Your output must be structured with clear bullet lists for maximum readability.""",

    "Problem": """You are an expert in PRD writing and analysis. 
Your task is to analyze the provided PRD and provide a detailed analysis of the problem section.

<PRD Content>
{prd_content}
</PRD Content>

<Retrieved Research Context>
{context}
</Retrieved Research Context>

Analyze the problem section by:
1. Evaluating whether the problem is clearly defined and measurable
2. Assessing the problem's business impact and market validation
3. Checking if the problem aligns with user needs based on research
4. Identifying gaps between stated problems and user pain points

CRITICAL FORMATTING: 
- Provide your analysis in clear BULLET POINTS format
- When referencing insights from Retrieved Research Context, you MUST include direct citations using format [Source: Document Name]
- Structure your response to include: analysis (bullet points), recommendations (bullet points), potential_pitfalls (bullet points), and supported_points (bullet points)

Your output must be structured with clear bullet lists for maximum readability.""",

    "Solution": """You are an expert in PRD writing and analysis. 
Your task is to analyze the provided PRD and provide a detailed analysis of the solution section.

<PRD Content>
{prd_content}
</PRD Content>

<Retrieved Research Context>
{context}
</Retrieved Research Context>

Analyze the solution section by:
1. Evaluating whether the solution addresses the core problem
2. Assessing solution feasibility and user experience
3. Checking alignment between solution and target audience
4. Validating solution approach against industry best practices and research

CRITICAL FORMATTING: 
- Provide your analysis in clear BULLET POINTS format
- When referencing insights from Retrieved Research Context, you MUST include direct citations using format [Source: Document Name]
- Structure your response to include: analysis (bullet points), recommendations (bullet points), potential_pitfalls (bullet points), and supported_points (bullet points)

Your output must be structured with clear bullet lists for maximum readability.""",

    "Go-To-Market": """You are an expert in PRD writing and analysis. 
Your task is to analyze the provided PRD and provide a detailed analysis of the go-to-market strategy.

<PRD Content>
{prd_content}
</PRD Content>

<Retrieved Research Context>
{context}
</Retrieved Research Context>

Analyze the go-to-market section by:
1. Evaluating the comprehensiveness and clarity of the GTM strategy
2. Assessing market positioning and competitive differentiation
3. Reviewing launch timeline and resource requirements
4. Validating strategy against market research and analytics data

CRITICAL FORMATTING: 
- Provide your analysis in clear BULLET POINTS format
- When referencing insights from Retrieved Research Context, you MUST include direct citations using format [Source: Document Name]
- Structure your response to include: analysis (bullet points), recommendations (bullet points), potential_pitfalls (bullet points), and supported_points (bullet points)

Your output must be structured with clear bullet lists for maximum readability.""",

    "Success Metrics": """You are an expert in PRD writing and analysis. 
Your task is to analyze the provided PRD and provide a detailed analysis of success metrics.

<PRD Content>
{prd_content}
</PRD Content>

<Retrieved Research Context>
{context}
</Retrieved Research Context>

Analyze the success metrics section by:
1. Evaluating whether metrics are specific, measurable, and achievable
2. Assessing alignment between metrics and business objectives
3. Checking if metrics cover both leading and lagging indicators
4. Validating metrics against industry benchmarks from research data

CRITICAL FORMATTING: 
- Provide your analysis in clear BULLET POINTS format
- When referencing insights from Retrieved Research Context, you MUST include direct citations using format [Source: Document Name]
- Structure your response to include: analysis (bullet points), recommendations (bullet points), potential_pitfalls (bullet points), and supported_points (bullet points)

Your output must be structured with clear bullet lists for maximum readability."""
}


def generate_report_plan(state: ReportState):
    """Generate the plan for PRD analysis sections."""
    
    # Define the sections to analyze (removed User Flow as requested)
    sections = [
        Section(
            name="Audience",
            description="Analysis of target audience definition and insights"
        ),
        Section(
            name="Problem", 
            description="Evaluation of problem definition and validation"
        ),
        Section(
            name="Solution",
            description="Assessment of proposed solution and approach"
        ),
        Section(
            name="Go-To-Market",
            description="Review of go-to-market strategy and execution plan"
        ),
        Section(
            name="Success Metrics",
            description="Analysis of success metrics and measurement approach"
        )
    ]
    
    return {
        "sections": sections, 
        "completed_sections": [], 
        "retrieval_logs": [], 
        "web_search_logs": [], 
        "market_suggestions": None,
        "final_report": ""
    }


def generate_queries(state: SectionState, config: RunnableConfig):
    """Generate RAG queries for a report section."""
    
    section = state["section"]
    prd_content = state["prd_content"]
    
    configurable = Configuration.from_runnable_config(config)
    number_of_queries = configurable.number_of_queries
    
    # Create query generation prompt for internal knowledge base
    query_prompt = f"""
    You are analyzing a PRD section: {section.name}
    
    PRD Content {prd_content}...
    
    Generate {number_of_queries} search queries to find relevant information from our internal research and analytics documents that would help evaluate this PRD section.
    
    These queries will search through our company's existing research documents, user studies, analytics reports, and strategic documents stored in our knowledge base.
    
    For {section.name} analysis, create queries that would find:
    - User research findings relevant to this {section.name.lower()}
    - Analytics data about user behavior patterns
    - Previous research insights about the target audience
    - Internal competitive analysis and market research
    - Strategic documents mentioning similar problems/solutions
    
    Write each query as if you're searching internal documents - use terms and concepts that would appear in our research reports, not general web search terms.
    
    Example good queries:
    - "research adhd purchasing behavior"
    - "analytics conversion funnel drop-off"
    - "research competitive analysis user needs"
    - "research retention"
    - "research adhd negative experience"

    Good queries are short and simple, so that retrieval focuses on key information. 
    
    Make queries specific to {section.name} but focused on internal knowledge retrieval.
    """
    
    # Initialize model
    writer_model = ChatOpenAI(
        model=configurable.writer_model,
        api_key=settings.openai_api_key
    )
    structured_llm = writer_model.with_structured_output(Queries)
    
    # Generate queries
    queries = structured_llm.invoke([
        SystemMessage(content=query_prompt),
        HumanMessage(content=f"Generate RAG queries for {section.name} analysis.")
    ])
    
    return {"search_queries": queries.queries}


def do_rag_retrieval(state: SectionState, config: RunnableConfig):
    """Perform RAG retrieval using native LangChain PGVector retriever."""
    
    search_queries = state["search_queries"]
    configurable = Configuration.from_runnable_config(config)
    section_name = state["section"].name
    
    # Store logs to return them for streaming
    retrieval_logs = []
    
    log_msg = f"🔍 Starting RAG retrieval for {section_name} section with {len(search_queries)} queries"
    print(log_msg)
    retrieval_logs.append(log_msg)
    
    # Get database session from config
    db = config.get("configurable", {}).get("db")
    if not db:
        # Fallback to getting db session
        db = next(get_db())
    
    # Create LangChain retriever (naive or contextual compression based on config)
    retriever = create_notion_retriever(db, top_k=configurable.top_k, retriever_type=configurable.retriever_type)
    
    # Retrieve documents for all queries
    all_docs = []
    total_retrieved = 0
    
    for i, query in enumerate(search_queries):
        try:
            log_msg = f"📚 Query {i+1}/{len(search_queries)}: '{query.search_query}'"
            print(log_msg)
            retrieval_logs.append(log_msg)
            
            docs = retriever.invoke(query.search_query)
            all_docs.extend(docs)
            total_retrieved += len(docs)
            
            log_msg = f"✅ Retrieved {len(docs)} documents for query {i+1}"
            print(log_msg)
            retrieval_logs.append(log_msg)
            
            # If no documents for this specific query, try a fallback
            if len(docs) == 0:
                log_msg = f"🔄 No documents for specific query, trying fallback general search..."
                print(log_msg)
                retrieval_logs.append(log_msg)
                
                fallback_docs = retriever.invoke("research analytics user behavior")
                all_docs.extend(fallback_docs[:2])  # Add just 2 fallback docs
                
                log_msg = f"🔄 Fallback retrieved {len(fallback_docs[:2])} additional documents"
                print(log_msg)
                retrieval_logs.append(log_msg)
                
        except Exception as e:
            log_msg = f"❌ Error retrieving for query '{query.search_query}': {e}"
            print(log_msg)
            retrieval_logs.append(log_msg)
            
            # Try fallback for failed queries too
            try:
                log_msg = f"🔄 Attempting fallback retrieval after error..."
                print(log_msg)
                retrieval_logs.append(log_msg)
                
                fallback_docs = retriever.invoke("research data analysis")
                all_docs.extend(fallback_docs[:1])  # Add just 1 fallback doc
                
                log_msg = f"🔄 Error fallback retrieved {len(fallback_docs[:1])} documents"
                print(log_msg)
                retrieval_logs.append(log_msg)
            except:
                log_msg = f"❌ Fallback retrieval also failed"
                print(log_msg)
                retrieval_logs.append(log_msg)
            continue
    
    log_msg = f"📊 Total documents retrieved: {total_retrieved}"
    print(log_msg)
    retrieval_logs.append(log_msg)
    
    # Remove duplicates and sort by relevance if available
    seen_content = set()
    unique_docs = []
    for doc in all_docs:
        content_hash = hash(doc.page_content[:100])  # Use first 100 chars as identifier
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_docs.append(doc)
    
    # Take top results
    top_docs = unique_docs[:configurable.top_k]
    log_msg = f"🎯 Using top {len(top_docs)} unique documents for {section_name} analysis"
    print(log_msg)
    retrieval_logs.append(log_msg)
    
    # Log document sources and store for final report
    sources_used = []
    if top_docs:
        log_msg = f"📄 Sources used for {section_name}:"
        print(log_msg)
        retrieval_logs.append(log_msg)
        
        for i, doc in enumerate(top_docs):
            source = doc.metadata.get('source', 'Unknown')
            page_type = doc.metadata.get('page_type', 'unknown')
            log_msg = f"   {i+1}. {source} ({page_type})"
            print(log_msg)
            retrieval_logs.append(log_msg)
            sources_used.append(f"{source} ({page_type})")
        
        source_str = "\n\n".join([
            f"**Source: {doc.metadata.get('source', 'Unknown')}** ({doc.metadata.get('page_type', 'unknown')})\n"
            f"{doc.page_content}"
            for doc in top_docs
        ])
    else:
        log_msg = f"⚠️  No relevant research documents found for {section_name}"
        print(log_msg)
        retrieval_logs.append(log_msg)
        source_str = "No relevant research documents found."
    
    return {"source_str": source_str, "sources_used": sources_used, "retrieval_logs": retrieval_logs}


async def write_section(state: SectionState, config: RunnableConfig) -> Command[Literal[END]]:
    """Write a section of the report using RAG context and structured output."""
    
    section = state["section"]
    source_str = state["source_str"]
    sources_used = state.get("sources_used", [])
    retrieval_logs = state.get("retrieval_logs", [])
    prd_content = state["prd_content"]
    
    configurable = Configuration.from_runnable_config(config)
    
    # Get appropriate instructions for this section
    instructions = SECTION_INSTRUCTIONS.get(section.name, SECTION_INSTRUCTIONS["Audience"])
    system_instructions = instructions.format(prd_content=prd_content, context=source_str)
    
    # Add debug logging to see what context is actually being passed
    print(f"🔬 DEBUG - {section.name} context length: {len(source_str)} chars")
    if source_str and source_str != "No relevant research documents found.":
        print(f"🔬 DEBUG - {section.name} context preview: {source_str[:200]}...")
    else:
        print(f"🔬 DEBUG - {section.name} has NO CONTEXT or empty context!")
    
    # Initialize model with structured output
    writer_model = ChatOpenAI(
        model=configurable.writer_model,
        api_key=settings.openai_api_key
    )
    structured_llm = writer_model.with_structured_output(AnalysisSection)
    
    # Generate structured analysis
    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=f"Analyze the {section.name} section of this PRD. Provide structured analysis, recommendations list, and score.")
    ])
    
    # Update section with structured results and sources
    section.analysis = result.analysis
    section.recommendations = result.recommendations
    section.potential_pitfalls = result.potential_pitfalls
    section.supported_points = result.supported_points
    section.score = result.score
    section.sources = sources_used
    
    return Command(
        update={"completed_sections": [section], "retrieval_logs": retrieval_logs},
        goto=END
    )


def generate_web_queries(state: MarketSuggestionsState, config: RunnableConfig):
    """Generate web search queries for market suggestions based on PRD content and completed analysis."""
    
    prd_content = state["prd_content"]
    completed_sections = state["completed_sections"]
    
    configurable = Configuration.from_runnable_config(config)
    
    # Create context from completed sections
    section_context = ""
    for section in completed_sections:
        if section.analysis:
            section_context += f"\n{section.name}: {section.analysis[:200]}..."
    
    # Create web query generation prompt
    query_prompt = f"""
    You are generating web search queries to find specific feature ideas, UX patterns, and design solutions that could improve a PRD's solution.
    
    PRD Content: {prd_content[:1000]}...
    
    Completed Analysis Context: {section_context}
    
    Generate exactly 3 web search queries to find:
    1. Specific feature ideas and functionality from similar products or apps that address this problem/audience
    2. UX/UI patterns, interface designs, and user experience solutions from relevant products
    3. Behavioral design techniques, interaction patterns, and usability improvements from successful apps
    
    These queries should help find tangible, actionable ideas that the product team can implement.
    Focus on finding:
    - Specific features that similar products use
    - UI/UX patterns that work well for this type of user/problem
    - Interaction design and behavioral nudges
    - Accessibility and usability best practices
    - Navigation patterns and information architecture
    - Onboarding flows and user engagement techniques
    
    Make queries specific to find concrete solutions, not general market analysis.
    
    Example good queries:
    - "[target audience] app features [specific problem] UX design"
    - "[similar app category] user interface patterns dashboard design"
    - "[behavioral goal] app design user engagement features"
    - "[specific functionality] UI patterns mobile web design"
    """
    
    # Initialize model
    writer_model = ChatOpenAI(
        model=configurable.writer_model,
        api_key=settings.openai_api_key
    )
    structured_llm = writer_model.with_structured_output(WebQueries)
    
    # Generate queries
    queries = structured_llm.invoke([
        SystemMessage(content=query_prompt),
        HumanMessage(content="Generate 3 web search queries for finding specific feature ideas, UX patterns, and design solutions.")
    ])
    
    return {"web_queries": queries.queries}


async def do_web_search(state: MarketSuggestionsState, config: RunnableConfig):
    """Perform web search using Tavily for market insights."""
    
    web_queries = state["web_queries"]
    web_search_logs = []
    
    log_msg = f"🌐 Starting web search for feature ideas and design solutions with {len(web_queries)} queries"
    print(log_msg)
    web_search_logs.append(log_msg)
    
    try:
        # Perform concurrent web searches
        search_results = await tavily_search_async(web_queries)
        
        total_results = sum(len(result.get('results', [])) for result in search_results)
        log_msg = f"🌐 Retrieved {total_results} web results across {len(search_results)} queries"
        print(log_msg)
        web_search_logs.append(log_msg)
        
        # Log individual query results
        for i, (query, result) in enumerate(zip(web_queries, search_results)):
            num_results = len(result.get('results', []))
            log_msg = f"🔍 Query {i+1}: '{query.search_query}' → {num_results} results"
            print(log_msg)
            web_search_logs.append(log_msg)
        
        # Format search results
        formatted_results = deduplicate_and_format_sources(search_results, max_tokens_per_source=500)
        
        log_msg = f"✅ Web search completed successfully"
        print(log_msg)
        web_search_logs.append(log_msg)
        
        return {
            "web_search_results": formatted_results,
            "web_search_logs": web_search_logs
        }
        
    except Exception as e:
        log_msg = f"❌ Error during web search: {e}"
        print(log_msg)
        web_search_logs.append(log_msg)
        
        return {
            "web_search_results": "No web search results available due to error.",
            "web_search_logs": web_search_logs
        }


async def write_market_suggestions(state: MarketSuggestionsState, config: RunnableConfig) -> Command[Literal[END]]:
    """Write feature and design suggestions section based on web search results."""
    
    prd_content = state["prd_content"]
    web_search_results = state["web_search_results"]
    web_search_logs = state.get("web_search_logs", [])
    completed_sections = state["completed_sections"]
    
    configurable = Configuration.from_runnable_config(config)
    
    # Create context from completed sections
    section_context = ""
    for section in completed_sections:
        if section.analysis:
            section_context += f"\n\n**{section.name} Analysis:**\n{section.analysis[:300]}..."
    
    # Market suggestions prompt
    system_instructions = f"""You are an expert in product design, UX/UI, and feature development.
    
    Based on the PRD content and web search results, provide specific feature ideas and design solutions that could improve the product.

    <PRD Content>
    {prd_content}
    </PRD Content>

    <Completed Analysis Context>
    {section_context}
    </Completed Analysis Context>

    <Web Search Results>
    {web_search_results}
    </Web Search Results>

    Provide actionable suggestions structured as:

    1. **Feature ideas** (4-6 bullet points):
       - Specific functionality and features found in similar products that could address the problem
       - Include source citations when based on web research using format [Source: Source Name]
       - Focus on concrete, implementable features
    
    2. **UX/UI suggestions** (4-6 bullet points):
       - Interface patterns, design approaches, and user experience solutions from successful products
       - Behavioral design techniques and interaction patterns
       - Include source citations when based on web research using format [Source: Source Name]
       - Focus on actionable design recommendations

    CRITICAL FORMATTING:
    - Always cite web sources when referencing external examples
    - Focus on tangible, implementable ideas
    - Connect suggestions directly to the PRD's audience and problem
    - Prioritize solutions that are practical and achievable

    Your suggestions should help the product team enhance their solution with proven patterns and innovative features from the broader ecosystem."""

    # Initialize model with structured output
    writer_model = ChatOpenAI(
        model=configurable.writer_model,
        api_key=settings.openai_api_key
    )
    structured_llm = writer_model.with_structured_output(MarketSuggestionsSection)
    
    # Generate structured market suggestions
    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Analyze similar products and provide structured feature ideas and UX/UI suggestions for this PRD.")
    ])
    
    # Extract sources from web search results for tracking
    sources_used = []
    if web_search_results and "Web Sources:" in web_search_results:
        # Extract source titles from formatted results
        lines = web_search_results.split('\n')
        for line in lines:
            if line.startswith('Source ') and ':' in line:
                source_title = line.split(':', 1)[1].strip()
                if source_title and source_title not in sources_used:
                    sources_used.append(source_title)
    
    # Create feature suggestions dict for final report
    market_suggestions = {
        "feature_ideas": result.feature_ideas,
        "ux_ui_suggestions": result.ux_ui_suggestions,
        "sources": sources_used
    }
    
    return Command(
        update={
            "market_suggestions": market_suggestions,
            "web_search_logs": web_search_logs
        },
        goto=END
    )


def initiate_section_analysis(state: ReportState):
    """Initiate parallel section analysis for ALL sections (force RAG for all)."""
    
    return [
        Send("analyze_section", {
            "prd_content": state["prd_content"],
            "prd_title": state.get("prd_title", "PRD"),
            "section": section,
            "search_iterations": 0,
            "search_queries": [],
            "source_str": "",
            "sources_used": [],
            "retrieval_logs": []
        })
        for section in state["sections"]  # Removed the research filter - analyze ALL sections
    ]





def compile_final_report(state: ReportState):
    """Compile the final analysis report with proper markdown formatting, sources, and market suggestions."""
    
    completed_sections = {s.name: s for s in state["completed_sections"]}
    market_suggestions = state.get("market_suggestions")
    all_sources = set()  # Collect all unique sources
    
    # Update sections with completed content
    for section in state["sections"]:
        if section.name in completed_sections:
            completed_section = completed_sections[section.name]
            section.analysis = completed_section.analysis
            section.recommendations = completed_section.recommendations
            section.potential_pitfalls = completed_section.potential_pitfalls
            section.supported_points = completed_section.supported_points
            section.score = completed_section.score
            section.sources = completed_section.sources
            all_sources.update(completed_section.sources)
    
    # Create final report with proper markdown
    report_parts = []
    report_parts.append("# PRD Analysis Report\n")
    
    # Add summary
    avg_score = sum(s.score for s in state["sections"]) / len(state["sections"])
    report_parts.append(f"**Overall Score: {avg_score:.1f}/5**\n")
    
    # Add each section with proper markdown formatting
    for section in state["sections"]:
        report_parts.append(f"## {section.name} (Score: {section.score}/5)\n")
        
        # Analysis section
        report_parts.append("### Analysis\n")
        report_parts.append(f"{section.analysis}\n")
        
        # Recommendations section
        report_parts.append("### Recommendations\n")
        if section.recommendations:
            for rec in section.recommendations:
                report_parts.append(f"- {rec}")
            report_parts.append("")  # Empty line
        else:
            report_parts.append("No specific recommendations provided.\n")
        
        # Potential Pitfalls section
        report_parts.append("### Potential Pitfalls\n")
        if section.potential_pitfalls:
            for pitfall in section.potential_pitfalls:
                report_parts.append(f"- {pitfall}")
            report_parts.append("")  # Empty line
        else:
            report_parts.append("No potential pitfalls identified.\n")
        
        # Supported Points section
        report_parts.append("### Supported Points\n")
        if section.supported_points:
            for point in section.supported_points:
                report_parts.append(f"- {point}")
            report_parts.append("")  # Empty line
        else:
            report_parts.append("No strongly supported points identified.\n")
        
        # Sources section (if any sources were used for this section)
        if section.sources:
            report_parts.append("### Sources Referenced\n")
            for source in section.sources:
                report_parts.append(f"- {source}")
            report_parts.append("")  # Empty line
    
    # Add Market Suggestions section at the end
    if market_suggestions:
        report_parts.append("---\n")
        report_parts.append("## Feature & Design Ideas\n")
        
        # Feature ideas
        report_parts.append("### Feature ideas:\n")
        if market_suggestions.get("feature_ideas"):
            for idea in market_suggestions["feature_ideas"]:
                report_parts.append(f"- {idea}")
            report_parts.append("")  # Empty line
        else:
            report_parts.append("No feature ideas identified.\n")
        
        # UX/UI suggestions
        report_parts.append("### UX/UI suggestions:\n")
        if market_suggestions.get("ux_ui_suggestions"):
            for suggestion in market_suggestions["ux_ui_suggestions"]:
                report_parts.append(f"- {suggestion}")
            report_parts.append("")  # Empty line
        else:
            report_parts.append("No UX/UI suggestions identified.\n")
        
        # Web sources section
        if market_suggestions.get("sources"):
            report_parts.append("### Web Sources Referenced\n")
            for source in market_suggestions["sources"]:
                report_parts.append(f"- {source}")
            report_parts.append("")  # Empty line
    
    # Add overall sources section at the end
    if all_sources:
        report_parts.append("---\n")
        report_parts.append("## Research Sources Used\n")
        report_parts.append("This analysis was informed by the following research documents:\n")
        for source in sorted(all_sources):
            report_parts.append(f"- {source}")
        report_parts.append("")
    
    final_report = "\n".join(report_parts)
    
    return {"final_report": final_report}


# Build the section analysis subgraph
section_builder = StateGraph(SectionState, output=SectionOutputState)
section_builder.add_node("generate_queries", generate_queries)
section_builder.add_node("do_rag_retrieval", do_rag_retrieval)
section_builder.add_node("write_section", write_section)

# Add edges for section subgraph (RAG is now ALWAYS used)
section_builder.add_edge(START, "generate_queries")
section_builder.add_edge("generate_queries", "do_rag_retrieval")
section_builder.add_edge("do_rag_retrieval", "write_section")

# Build the market suggestions subgraph
market_suggestions_builder = StateGraph(MarketSuggestionsState)
market_suggestions_builder.add_node("generate_web_queries", generate_web_queries)
market_suggestions_builder.add_node("do_web_search", do_web_search)
market_suggestions_builder.add_node("write_market_suggestions", write_market_suggestions)

# Add edges for market suggestions subgraph
market_suggestions_builder.add_edge(START, "generate_web_queries")
market_suggestions_builder.add_edge("generate_web_queries", "do_web_search")
market_suggestions_builder.add_edge("do_web_search", "write_market_suggestions")

# Build the main graph
builder = StateGraph(ReportState, input=ReportStateInput, output=ReportStateOutput, config_schema=Configuration)
builder.add_node("generate_report_plan", generate_report_plan)
builder.add_node("analyze_section", section_builder.compile())
builder.add_node("find_market_suggestions", market_suggestions_builder.compile())  # Now generates feature & design ideas
builder.add_node("compile_final_report", compile_final_report)

# Add edges for main graph - UPDATED PIPELINE: 
# generate_report_plan -> analyze_section -> find_market_suggestions (feature & design ideas) -> compile_final_report
builder.add_edge(START, "generate_report_plan")
builder.add_conditional_edges("generate_report_plan", initiate_section_analysis, ["analyze_section"])
builder.add_edge("analyze_section", "find_market_suggestions")
builder.add_edge("find_market_suggestions", "compile_final_report")
builder.add_edge("compile_final_report", END)

# Compile the final graph
prd_analysis_graph = builder.compile()

# Async wrapper for streaming
async def analyze_prd_with_streaming(prd_content: str, prd_title: str = "PRD", db: Session = None, current_user = None):
    """Analyze PRD with streaming support using LangChain retrievers (naive or contextual compression) and Tavily web search."""
    
    # Get user's retriever type from their notion settings, fallback to global default
    user_retriever_type = settings.retriever_type  # Default fallback
    
    if current_user and db:
        try:
            from app.crud.notion import get_user_notion_settings
            user_settings = get_user_notion_settings(db, current_user.id)
            if user_settings and user_settings.retriever_type:
                # Convert string to enum
                user_retriever_type = RetrieverType(user_settings.retriever_type)
                print(f"🔧 Using user's retriever type: {user_retriever_type.value}")
        except Exception as e:
            print(f"⚠️ Failed to get user's retriever type, using default: {e}")
    
    config = {
        "configurable": {
            "top_k": 5, 
            "db": db,
            "retriever_type": user_retriever_type  # Use user's specific setting
        }
    }
    
    async for chunk in prd_analysis_graph.astream(
        {"prd_content": prd_content, "prd_title": prd_title},
        config=config
    ):
        yield chunk