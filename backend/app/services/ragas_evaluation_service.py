"""
RAGAS Evaluation Service for RAG pipeline evaluation.

This service provides:
1. Synthetic Dataset Generation (SDG) using RAGAS
2. RAG Evaluation using RAGAS metrics
3. Comparison between Naive and Contextual Compression retrievers
4. Async processing for long-running evaluations
"""

import asyncio
import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from sqlalchemy.orm import Session
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import pandas as pd # Added for pandas

# Local imports
from app.core.config import settings, RetrieverType
from app.database.connection import get_db
from app.models.notion_chunk import NotionChunk
from app.models.notion_page import NotionPage, PageType
from app.services.prd_review_agent import create_notion_retriever


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    GENERATING_DATASET = "generating_dataset"
    EVALUATING_NAIVE = "evaluating_naive"
    EVALUATING_COMPRESSION = "evaluating_compression"
    COMPLETED = "completed"
    FAILED = "failed"


def _run_in_thread_with_new_loop(sync_func, *args, **kwargs):
    """Run a sync function in a separate thread with its own event loop to avoid uvloop conflicts."""
    
    result_container = {}
    exception_container = {}
    
    def run_in_thread():
        try:
            print(f"🧵 Starting {sync_func.__name__} in separate thread (PID: {threading.current_thread().ident})")
            
            # Create a new event loop for this thread (not uvloop)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = sync_func(*args, **kwargs)
                result_container['result'] = result
                print(f"✅ {sync_func.__name__} completed successfully in thread")
            finally:
                loop.close()
                
        except Exception as e:
            print(f"❌ Error in {sync_func.__name__} thread: {e}")
            exception_container['exception'] = e
    
    # Run in separate thread
    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()
    
    # Check for exceptions
    if 'exception' in exception_container:
        raise exception_container['exception']
    
    return result_container['result']


def _initialize_ragas_components_sync():
    """Initialize all RAGAS components in a separate thread to avoid nest_asyncio conflicts."""
    
    import os
    
    print(f"🔬 Initializing all RAGAS components in separate thread...")
    
    # CRITICAL: Set environment variables in this thread
    # RAGAS internally creates OpenAI clients that rely on environment variables
    openai_api_key = settings.openai_api_key
    if not openai_api_key:
        raise ValueError("OpenAI API key not configured in settings")
    
    # Set environment variables in this thread
    os.environ['OPENAI_API_KEY'] = openai_api_key
    if settings.langsmith_api_key:
        os.environ['LANGSMITH_API_KEY'] = settings.langsmith_api_key
    
    print(f"🔑 Set environment variables in thread - OPENAI_API_KEY: {len(openai_api_key)} chars")
    
    # Import RAGAS components
    ragas_components = _lazy_import_ragas()
    
    print(f"🔑 Using OpenAI API key for RAGAS components (length: {len(openai_api_key)} chars)")
    
    # Initialize LLMs with RAGAS wrappers (this is where nest_asyncio.apply() gets called)
    # Explicitly pass API key instead of relying on environment variables
    generator_llm = ragas_components['LangchainLLMWrapper'](
        ChatOpenAI(model="gpt-4.1-mini", api_key=openai_api_key)  # Fixed: Valid model name
    )
    generator_embeddings = ragas_components['LangchainEmbeddingsWrapper'](
        OpenAIEmbeddings(api_key=openai_api_key)  # Explicit API key
    )
    evaluator_llm = ragas_components['LangchainLLMWrapper'](
        ChatOpenAI(model="gpt-4.1-mini", api_key=openai_api_key)  # Fixed: Valid model name
    )
    
    # Initialize LangSmith client if available
    langsmith_client = None
    if settings.langsmith_api_key:
        LangSmithClient = _lazy_import_langsmith()
        if LangSmithClient:
            print(f"🔗 Initializing LangSmith client...")
            try:
                # Pass LangSmith API key explicitly
                langsmith_client = LangSmithClient(api_key=settings.langsmith_api_key)
                print(f"✅ LangSmith client initialized successfully")
            except Exception as e:
                print(f"⚠️ Failed to initialize LangSmith client: {e}")
                langsmith_client = None
    else:
        print(f"⚠️ No LangSmith API key configured, experiments will be skipped")
    
    print(f"✅ All RAGAS components initialized successfully in thread")
    
    return {
        'ragas_components': ragas_components,
        'generator_llm': generator_llm,
        'generator_embeddings': generator_embeddings,
        'evaluator_llm': evaluator_llm,
        'langsmith_client': langsmith_client
    }


def _generate_synthetic_dataset_sync(components, documents, testset_size):
    """Synchronous RAGAS dataset generation that runs in a separate thread."""
    
    import os
    
    # CRITICAL: Set environment variables for this thread too
    os.environ['OPENAI_API_KEY'] = settings.openai_api_key
    if settings.langsmith_api_key:
        os.environ['LANGSMITH_API_KEY'] = settings.langsmith_api_key
    
    print(f"🔬 Creating RAGAS TestsetGenerator in thread...")
    
    # Initialize RAGAS TestsetGenerator
    generator = components['ragas_components']['TestsetGenerator'](
        llm=components['generator_llm'],
        embedding_model=components['generator_embeddings']
    )
    
    print(f"🔬 Generating synthetic dataset with {testset_size} samples from {len(documents)} documents")
    
    # Generate synthetic dataset
    dataset = generator.generate_with_langchain_docs(
        documents,
        testset_size=testset_size
    )
    
    print(f"✅ Dataset generation completed with {len(dataset)} samples")
    return dataset


def _evaluate_with_ragas_sync(components, eval_dataset, metrics):
    """Synchronous RAGAS evaluation that runs in a separate thread."""
    
    import os
    
    # CRITICAL: Set environment variables for this thread
    # This is where the API key error was happening!
    os.environ['OPENAI_API_KEY'] = settings.openai_api_key
    if settings.langsmith_api_key:
        os.environ['LANGSMITH_API_KEY'] = settings.langsmith_api_key
    
    print(f"📊 Running RAGAS evaluation with {len(metrics)} metrics")
    print(f"🔑 Environment OPENAI_API_KEY set in evaluation thread: {len(os.environ.get('OPENAI_API_KEY', ''))} chars")
    
    # Run evaluation
    result = components['ragas_components']['evaluate'](
        dataset=eval_dataset,
        metrics=metrics,
        llm=components['evaluator_llm']
    )
    
    return result


def _lazy_import_ragas():
    """Lazy import RAGAS components to avoid nest_asyncio conflicts with uvloop."""
    try:
        # Import RAGAS components when actually needed
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.testset import TestsetGenerator
        from ragas import evaluate
        from ragas.metrics import (
            LLMContextRecall,
            Faithfulness,
            FactualCorrectness,
            ResponseRelevancy,
            ContextEntityRecall,
            NoiseSensitivity,
            ContextPrecision
        )
        from datasets import Dataset
        
        return {
            'LangchainLLMWrapper': LangchainLLMWrapper,
            'LangchainEmbeddingsWrapper': LangchainEmbeddingsWrapper,
            'TestsetGenerator': TestsetGenerator,
            'evaluate': evaluate,
            'LLMContextRecall': LLMContextRecall,
            'Faithfulness': Faithfulness,
            'FactualCorrectness': FactualCorrectness,
            'ResponseRelevancy': ResponseRelevancy,
            'ContextEntityRecall': ContextEntityRecall,
            'NoiseSensitivity': NoiseSensitivity,
            'ContextPrecision': ContextPrecision,
            'Dataset': Dataset
        }
    except ImportError as e:
        raise ImportError(f"RAGAS dependencies not installed: {e}")


def _lazy_import_langsmith():
    """Lazy import LangSmith client."""
    try:
        from langsmith import Client
        return Client
    except ImportError:
        return None


class RagasEvaluationService:
    """Service for running RAGAS evaluations on RAG pipeline."""
    
    def __init__(self):
        # Store evaluation state
        self.evaluation_state = {
            "status": EvaluationStatus.PENDING,
            "progress": 0,
            "current_step": "",
            "results": {},
            "error": None,
            "start_time": None,
            "end_time": None
        }
        
        # Components will be initialized in separate thread when needed
        self._components = None
    
    async def _init_components_async(self):
        """Initialize RAGAS components asynchronously in a separate thread."""
        if self._components is None:
            print(f"🧵 Initializing RAGAS components in separate thread to avoid uvloop conflicts...")
            self._components = await asyncio.to_thread(
                _run_in_thread_with_new_loop,
                _initialize_ragas_components_sync
            )
    
    @property
    async def components(self):
        await self._init_components_async()
        return self._components
    
    def get_notion_documents_for_user(self, db: Session, user_id: int = 4, limit: int = 20) -> List[Document]:
        """Get notion documents for SDG from user's research and analytics chunks."""
        
        chunks_with_pages = (
            db.query(NotionChunk, NotionPage)
            .join(NotionPage, NotionChunk.page_id == NotionPage.id)
            .filter(NotionPage.user_id == user_id)
            .filter(NotionPage.page_type.in_([PageType.research, PageType.analytics]))
            .filter(NotionChunk.embedding.isnot(None))
            .limit(limit)
            .all()
        )
        
        documents = []
        for chunk, page in chunks_with_pages:
            doc = Document(
                page_content=chunk.content,
                metadata={
                    "source": page.title,
                    "page_type": page.page_type.value,
                    "notion_page_id": page.notion_page_id,
                    "chunk_id": chunk.id,
                    "user_id": user_id
                }
            )
            documents.append(doc)
        
        print(f"📚 Retrieved {len(documents)} documents for RAGAS evaluation")
        return documents
    
    async def generate_synthetic_dataset(self, db: Session, user_id: int = 4, testset_size: int = 1):
        """Generate synthetic dataset using RAGAS SDG."""
        
        print(f"🧪 Starting synthetic dataset generation for user {user_id}")
        self.evaluation_state["current_step"] = f"Fetching documents for user {user_id}"
        
        # Get documents for SDG
        documents = self.get_notion_documents_for_user(db, user_id, limit=20)
        
        if not documents:
            raise ValueError(f"No documents found for user {user_id}")
        
        self.evaluation_state["current_step"] = "Initializing RAGAS components in separate thread"
        
        # Initialize components in separate thread
        components = await self.components
        
        self.evaluation_state["current_step"] = "Generating synthetic dataset"
        
        print(f"🔬 Running RAGAS dataset generation in separate thread...")
        
        # Run RAGAS in separate thread with its own event loop
        dataset = await asyncio.to_thread(
            _run_in_thread_with_new_loop,
            _generate_synthetic_dataset_sync,
            components,
            documents,
            testset_size
        )
        
        print(f"✅ Generated synthetic dataset with {len(dataset)} samples")
        
        # Store in LangSmith if available
        print(f"🔍 Checking LangSmith dataset storage...")
        print(f"🔍 LangSmith client available: {components['langsmith_client'] is not None}")
        
        if components['langsmith_client']:
            print(f"✅ LangSmith client available, storing dataset...")
            try:
                await self._store_dataset_in_langsmith(dataset, f"RGRAG_{user_id}", components['langsmith_client'])
                print(f"✅ Dataset storage completed successfully")
            except Exception as e:
                print(f"❌ FAILED to store dataset: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ No LangSmith client available for dataset storage")
        
        return dataset
    
    async def _store_dataset_in_langsmith(self, dataset, dataset_name: str, langsmith_client):
        """Store the synthetic dataset in LangSmith."""
        
        try:
            print(f"🔗 Storing dataset in LangSmith: {dataset_name}")
            
            # Create dataset in LangSmith
            langsmith_dataset = await asyncio.to_thread(
                langsmith_client.create_dataset,
                dataset_name=dataset_name,
                description=f"RAGAS Synthetic Dataset generated at {datetime.now()}"
            )
            
            # Add examples to dataset
            dataset_df = dataset.to_pandas()
            for _, row in dataset_df.iterrows():
                await asyncio.to_thread(
                    langsmith_client.create_example,
                    inputs={"question": row["user_input"]},
                    outputs={"answer": row["reference"]},
                    metadata={"context": row["reference_contexts"]},
                    dataset_id=langsmith_dataset.id
                )
            
            print(f"✅ Dataset stored in LangSmith with {len(dataset_df)} examples")
            
        except Exception as e:
            print(f"⚠️ Failed to store dataset in LangSmith: {e}")
    
    async def evaluate_full_pipeline(
        self, 
        db: Session, 
        dataset, 
        retriever_type: RetrieverType,
        user_id: int = 4
    ) -> Dict[str, Any]:
        """Evaluate the FULL PRD review pipeline using RAGAS metrics."""
        
        print(f"🎯 Starting evaluation for {retriever_type.value.upper()} retriever pipeline")
        step_message = f"Evaluating complete system with {retriever_type.value.upper()} retriever"
        self.evaluation_state["current_step"] = step_message
        
        # CRITICAL DEBUG: Check if we have documents in the database
        print(f"🔍 DEBUGGING: Checking database for retrieval documents...")
        try:
            from app.models.notion_chunk import NotionChunk
            from app.models.notion_page import NotionPage, PageType
            
            chunks_with_pages = (
                db.query(NotionChunk, NotionPage)
                .join(NotionPage, NotionChunk.page_id == NotionPage.id)
                .filter(NotionPage.user_id == user_id)
                .filter(NotionPage.page_type.in_([PageType.research, PageType.analytics]))
                .filter(NotionChunk.embedding.isnot(None))
                .limit(10)
                .all()
            )
            
            print(f"📊 Database check: Found {len(chunks_with_pages)} chunks with embeddings for user {user_id}")
            if len(chunks_with_pages) > 0:
                sample_chunk = chunks_with_pages[0][0]
                sample_page = chunks_with_pages[0][1]
                print(f"   Sample chunk: {sample_chunk.content[:100]}...")
                print(f"   Sample page: {sample_page.title} ({sample_page.page_type.value})")
            else:
                print(f"❌ CRITICAL: No chunks found for user {user_id}! This explains empty contexts.")
                print(f"   Check if:")
                print(f"   1. User {user_id} has imported Notion data")
                print(f"   2. Pages are marked as 'research' or 'analytics' type")
                print(f"   3. Chunks have embeddings generated")
                
        except Exception as e:
            print(f"❌ Error checking database: {e}")
        
        # Test the retriever directly
        print(f"🔍 DEBUGGING: Testing retriever directly...")
        try:
            from app.services.prd_review_agent import create_notion_retriever
            test_retriever = create_notion_retriever(db, top_k=5, retriever_type=retriever_type)
            if test_retriever:
                print(f"✅ Retriever created successfully for {retriever_type.value}")
                
                # Test with a simple query
                test_query = "ADHD medication management research"
                test_results = await asyncio.to_thread(test_retriever.invoke, test_query)
                print(f"🔍 Direct retriever test results: {len(test_results)} documents")
                if test_results:
                    print(f"   Sample result: {test_results[0].page_content[:100]}...")
                else:
                    print(f"⚠️ Direct retriever test returned empty results")
            else:
                print(f"❌ Failed to create retriever for {retriever_type.value}")
        except Exception as e:
            print(f"❌ Error testing retriever: {e}")
            import traceback
            traceback.print_exc()
        
        # Get components
        components = await self.components
        
        # Import PRD review agent components
        from app.services.prd_review_agent import analyze_prd_with_streaming
        
        # Prepare evaluation dataset
        evaluation_data = []
        dataset_df = dataset.to_pandas()
        
        print(f"🔍 Processing {len(dataset_df)} test samples through {retriever_type.value.upper()} pipeline")
        
        for idx, row in dataset_df.iterrows():
            question = row["user_input"]
            reference = row["reference"] 
            reference_contexts = row["reference_contexts"]
            
            print(f"🔍 Processing sample {idx+1}/{len(dataset_df)}")
            print(f"   Question: {question[:100]}...")
            print(f"   Expected ground truth: {reference[:100]}...")
            
            # Create a mock PRD content based on the question for pipeline testing
            # Make it more comprehensive to trigger retrieval
            mock_prd_content = f"""
# PRD Analysis Request

## Question/Focus Area
{question}

## Problem Statement
We need to analyze this PRD section with comprehensive research insights. The focus area is: {question}

## Research Requirements
This analysis requires retrieving relevant research data, user studies, analytics, and market insights to provide evidence-based recommendations.

## Context for Analysis
Please analyze this PRD section and provide insights based on the retrieved research context. Use all available research data to support the analysis.

## Background
{reference[:200]}

## Analysis Focus
The analysis should cover all aspects related to: {question}
"""

            print(f"📝 Mock PRD content length: {len(mock_prd_content)} chars")
            print(f"📝 Mock PRD preview: {mock_prd_content[:200]}...")

            try:
                # Run through the FULL PRD review pipeline
                print(f"📋 Running question {idx+1}/{len(dataset_df)} through {retriever_type.value.upper()} pipeline...")
                
                config = {
                    "configurable": {
                        "top_k": 5, 
                        "db": db,
                        "retriever_type": retriever_type,
                        "number_of_queries": 3,  # Increase queries for better retrieval
                    }
                }
                
                print(f"🔧 Pipeline config: {config}")
                
                # Create a simple mock user for the pipeline
                class MockUser:
                    def __init__(self, user_id):
                        self.id = user_id
                
                mock_user = MockUser(user_id)
                print(f"👤 Mock user ID: {mock_user.id}")
                
                # Collect the pipeline output
                pipeline_response = ""
                retrieved_contexts = []
                
                print(f"🔄 Starting pipeline streaming for sample {idx+1}...")
                chunk_count = 0
                async for chunk in analyze_prd_with_streaming(
                    mock_prd_content, 
                    f"Test PRD {idx+1}", 
                    db, 
                    mock_user,
                    override_retriever_type=retriever_type  # CRITICAL: Override user's setting
                ):
                    chunk_count += 1
                    print(f"🔄 Received chunk {chunk_count} with nodes: {list(chunk.keys())}")
                    
                    # Extract final report from the pipeline response
                    for node_name, data in chunk.items():
                        print(f"   Node: {node_name}, Keys: {list(data.keys()) if isinstance(data, dict) else 'Not dict'}")
                        
                        # Look for ANY retrieval-related data
                        if isinstance(data, dict):
                            for key, value in data.items():
                                if 'retrieval' in key.lower() or 'source' in key.lower() or 'context' in key.lower():
                                    print(f"🔍 Found retrieval-related key '{key}': {type(value)} - {len(str(value)) if value else 'Empty'}")
                                    if value and isinstance(value, str) and len(value) > 10:
                                        print(f"     Content preview: {str(value)[:100]}...")
                        
                        if node_name == "compile_final_report" and "final_report" in data:
                            pipeline_response = data["final_report"]
                            print(f"✅ Got final report: {len(pipeline_response)} chars")
                        
                        # Also collect retrieval contexts for context evaluation
                        if "source_str" in data and data["source_str"]:
                            print(f"🔍 Found source_str in {node_name}: {len(data['source_str'])} chars")
                            # Extract actual document content from retrieval
                            contexts = data["source_str"].split("**Source:")
                            for context in contexts[1:]:  # Skip first empty split
                                context_content = context.split("\n", 1)[-1] if "\n" in context else context
                                if context_content.strip():
                                    retrieved_contexts.append(context_content.strip()[:500])  # Limit length
                                    print(f"   Added context: {len(context_content.strip())} chars")
                        
                        # ALSO check completed sections for source contexts
                        if "completed_sections" in data and data["completed_sections"]:
                            for completed_section in data["completed_sections"]:
                                if hasattr(completed_section, 'source_contexts') and completed_section.source_contexts:
                                    print(f"🔍 Found source_contexts in completed section {completed_section.name}: {len(completed_section.source_contexts)} chars")
                                    # Extract contexts from completed section
                                    section_contexts = completed_section.source_contexts.split("**Source:")
                                    for context in section_contexts[1:]:  # Skip first empty split
                                        context_content = context.split("\n", 1)[-1] if "\n" in context else context
                                        if context_content.strip():
                                            retrieved_contexts.append(context_content.strip()[:500])  # Limit length
                                            print(f"   Added section context: {len(context_content.strip())} chars")
                
                print(f"🔄 Streaming completed for sample {idx+1} - Total chunks: {chunk_count}")
                
                # If no response was captured, create a fallback
                if not pipeline_response:
                    pipeline_response = "No analysis generated by pipeline"
                
                # Remove duplicates from retrieved contexts
                retrieved_contexts = list(dict.fromkeys(retrieved_contexts))[:5]  # Max 5 unique contexts
                
                print(f"🔍 Sample {idx+1} - Retrieved contexts: {len(retrieved_contexts)}")
                if len(retrieved_contexts) == 0:
                    print(f"⚠️ WARNING: No contexts retrieved for sample {idx+1}")
                    print(f"   Question: {question[:100]}...")
                    print(f"   Retriever type: {retriever_type.value}")
                else:
                    print(f"✅ Sample {idx+1} - Contexts retrieved successfully")
                
                evaluation_data.append({
                    "question": question,
                    "answer": pipeline_response,  # ACTUAL pipeline response
                    "contexts": retrieved_contexts,
                    "ground_truth": reference,
                    "reference_contexts": reference_contexts
                })
                
                print(f"✅ {retriever_type.value.upper()} pipeline evaluation {idx+1} completed - Response length: {len(pipeline_response)} chars")
                
            except Exception as e:
                print(f"❌ Error in {retriever_type.value.upper()} pipeline evaluation for question {idx+1}: {e}")
                # Add empty result for failed pipeline runs
                evaluation_data.append({
                    "question": question,
                    "answer": f"Pipeline evaluation failed: {str(e)}",
                    "contexts": [],
                    "ground_truth": reference,
                    "reference_contexts": reference_contexts
                })
        
        # Convert to RAGAS dataset format
        eval_dataset = components['ragas_components']['Dataset'].from_list(evaluation_data)
        
        # Define RAGAS metrics for full pipeline evaluation
        metrics = [
            components['ragas_components']['ContextPrecision'](),
            components['ragas_components']['LLMContextRecall'](), 
            components['ragas_components']['Faithfulness'](),
            components['ragas_components']['ResponseRelevancy'](),
            # Note: Removing ContextEntityRecall and NoiseSensitivity as they may not work well with full pipeline responses
        ]
        
        print(f"📊 Running RAGAS evaluation on {retriever_type.value.upper()} pipeline with {len(metrics)} metrics")
        
        # Run evaluation
        try:
            result = await asyncio.to_thread(
                _run_in_thread_with_new_loop,
                _evaluate_with_ragas_sync,
                components,
                eval_dataset,
                metrics
            )
            
            print(f"📊 RAGAS evaluation completed for {retriever_type.value.upper()}")
            print(f"🔍 Result type: {type(result)}")
            
            # Convert result to dict - handle EvaluationResult object
            result_dict = {
                "retriever_type": retriever_type.value,
                "evaluation_type": "full_pipeline",
                "metrics": {},
                "samples_evaluated": len(evaluation_data),
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract metric scores from EvaluationResult
            try:
                # RAGAS returns an EvaluationResult object, not a dict
                if hasattr(result, 'to_pandas'):
                    # Convert to pandas and extract scores
                    result_df = result.to_pandas()
                    print(f"📊 Result DataFrame shape: {result_df.shape}")
                    print(f"📊 Result DataFrame columns: {list(result_df.columns)}")
                    
                    # Extract mean scores for each metric
                    for column in result_df.columns:
                        if column not in ['question', 'answer', 'contexts', 'ground_truth']:
                            try:
                                mean_score = result_df[column].mean()
                                if not pd.isna(mean_score):
                                    result_dict["metrics"][column] = float(mean_score)
                                    print(f"📊 {column}: {mean_score:.3f}")
                                else:
                                    print(f"⚠️ {column}: NaN (evaluation failed)")
                            except Exception as e:
                                print(f"⚠️ Failed to extract {column}: {e}")
                
                elif hasattr(result, '__dict__'):
                    # Try to extract from object attributes
                    for attr_name, attr_value in result.__dict__.items():
                        if isinstance(attr_value, (int, float)):
                            result_dict["metrics"][attr_name] = float(attr_value)
                
                else:
                    # Fallback: try to iterate if it's dict-like
                    for metric_name, score in result.items():
                        if isinstance(score, (int, float)):
                            result_dict["metrics"][metric_name] = float(score)
                        else:
                            result_dict["metrics"][metric_name] = str(score)
                            
            except Exception as e:
                print(f"⚠️ Error extracting metrics from result: {e}")
                result_dict["metrics"]["error"] = str(e)
                print(f"🔍 Result object methods: {[method for method in dir(result) if not method.startswith('_')]}")
            
            print(f"✅ {retriever_type.value.upper()} pipeline evaluation completed")
            print(f"📊 Final metrics: {result_dict['metrics']}")
            
            # IMMEDIATELY store results to prevent data loss
            await self._store_results_persistently(result_dict, retriever_type)
            
            # Store results as LangSmith experiment
            print(f"🔍 Checking LangSmith experiment storage for {retriever_type.value.upper()}...")
            print(f"🔍 LangSmith client available: {components['langsmith_client'] is not None}")
            print(f"🔍 LangSmith API key configured: {bool(settings.langsmith_api_key)}")
            
            if components['langsmith_client']:
                print(f"✅ LangSmith client available, creating experiment...")
                try:
                    await self._store_experiment_in_langsmith(
                        result_dict, 
                        eval_dataset, 
                        retriever_type, 
                        components['langsmith_client']
                    )
                    print(f"✅ Experiment storage completed for {retriever_type.value.upper()}")
                except Exception as e:
                    print(f"❌ FAILED to store experiment for {retriever_type.value.upper()}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️ No LangSmith client available for {retriever_type.value.upper()}")
                print(f"   - LangSmith API key length: {len(settings.langsmith_api_key) if settings.langsmith_api_key else 0}")
                print(f"   - Check LANGSMITH_API_KEY configuration")
            
            return result_dict
            
        except Exception as e:
            print(f"❌ Error during {retriever_type.value.upper()} pipeline evaluation: {e}")
            import traceback
            traceback.print_exc()
            error_result = {
                "retriever_type": retriever_type.value,
                "evaluation_type": "full_pipeline",
                "error": str(e),
                "samples_evaluated": len(evaluation_data),
                "timestamp": datetime.now().isoformat()
            }
            
            # Store error results too
            await self._store_results_persistently(error_result, retriever_type)
            return error_result

    async def _store_results_persistently(self, result_dict: Dict[str, Any], retriever_type: RetrieverType):
        """Store evaluation results immediately to prevent data loss."""
        try:
            import json
            import os
            
            # Create results directory if it doesn't exist
            results_dir = "ragas_results"
            os.makedirs(results_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{results_dir}/ragas_evaluation_{retriever_type.value}_{timestamp}.json"
            
            # Store results
            with open(filename, 'w') as f:
                json.dump(result_dict, f, indent=2)
            
            print(f"💾 Results stored persistently: {filename}")
            
        except Exception as e:
            print(f"⚠️ Failed to store results persistently: {e}")

    async def _store_experiment_in_langsmith(
        self, 
        result_dict: Dict[str, Any], 
        eval_dataset, 
        retriever_type: RetrieverType,
        langsmith_client
    ):
        """Store evaluation results as LangSmith experiment."""
        
        print(f"🧪 Starting LangSmith experiment creation for {retriever_type.value.upper()}")
        
        if not langsmith_client:
            print(f"❌ CRITICAL: No LangSmith client provided")
            return
            
        try:
            print(f"🔄 Step 1: Generating experiment name...")
            # Create experiment name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            experiment_name = f"RAGAS_Evaluation_{retriever_type.value.upper()}_{timestamp}"
            
            print(f"📝 Step 2: Experiment name generated: {experiment_name}")
            print(f"🔄 Step 3: Creating experiment in LangSmith...")
            
            # Create experiment in LangSmith
            experiment = await asyncio.to_thread(
                langsmith_client.create_experiment,
                experiment_name=experiment_name,
                description=f"RAGAS evaluation of {retriever_type.value} retriever pipeline - Full PRD review system test"
            )
            
            print(f"✅ Step 4: Experiment created successfully!")
            print(f"🆔 Experiment ID: {experiment.id}")
            print(f"📝 Experiment Name: {experiment.name}")
            
            print(f"🔄 Step 5: Preparing experiment metadata...")
            experiment_metadata = {
                "evaluation_results": result_dict,
                "retriever_type": retriever_type.value,
                "evaluation_type": "full_pipeline",
                "ragas_metrics": list(result_dict.get("metrics", {}).keys()),
                "samples_evaluated": result_dict.get("samples_evaluated", 0),
                "timestamp": result_dict.get("timestamp", ""),
                "ragas_version": "ragas_evaluation_v1.0"
            }
            
            print(f"🔄 Step 6: Updating experiment with metadata...")
            await asyncio.to_thread(
                langsmith_client.update_experiment,
                experiment_id=experiment.id,
                metadata=experiment_metadata
            )
            
            print(f"✅ Step 7: Experiment metadata updated successfully")
            
            # Try to add dataset examples to experiment as runs
            try:
                print(f"🔄 Step 8: Adding evaluation runs to experiment...")
                dataset_df = eval_dataset.to_pandas()
                print(f"📊 Dataset has {len(dataset_df)} samples, adding first 3 as runs...")
                
                for idx, row in dataset_df.iterrows():
                    if idx >= 1:  # Only add first 3 examples to avoid overwhelming
                        break
                        
                    # Create a run for this evaluation sample
                    run_name = f"{experiment_name}_sample_{idx+1}"
                    print(f"🔄 Creating run {idx+1}: {run_name}")
                    
                    await asyncio.to_thread(
                        langsmith_client.create_run,
                        name=run_name,
                        inputs={"question": row["question"]},
                        outputs={"answer": row["answer"]},
                        experiment_name=experiment_name,
                        metadata={
                            "retriever_type": retriever_type.value,
                            "sample_index": idx,
                            "ground_truth": row["ground_truth"]
                        }
                    )
                    print(f"✅ Run {idx+1} created successfully")
                
                print(f"✅ Step 9: Added {min(1, len(dataset_df))} evaluation runs to experiment")
                
            except Exception as run_error:
                print(f"⚠️ Step 8-9 WARNING: Failed to add runs to experiment (non-critical): {run_error}")
                print(f"📝 This doesn't affect the main experiment creation")
            
            print(f"🎉 SUCCESS: LangSmith experiment '{experiment_name}' created completely!")
            print(f"🔗 You can find it in LangSmith with ID: {experiment.id}")
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: Failed to create LangSmith experiment for {retriever_type.value.upper()}")
            print(f"🔍 Error type: {type(e).__name__}")
            print(f"🔍 Error message: {str(e)}")
            import traceback
            print(f"🔍 Full traceback:")
            traceback.print_exc()
            # Don't raise - this is not critical for evaluation success

    async def run_full_evaluation(self, db: Session, user_id: int = 4, testset_size: int = 6) -> Dict[str, Any]:
        """Run complete RAGAS evaluation pipeline with FULL PRD review pipeline testing."""
        
        try:
            self.evaluation_state.update({
                "status": EvaluationStatus.GENERATING_DATASET,
                "progress": 0,
                "start_time": datetime.now().isoformat(),
                "error": None,
                "current_step": "Starting RAGAS evaluation pipeline"
            })
            
            # Step 1: Generate synthetic dataset
            print("🚀 Starting RAGAS evaluation pipeline (FULL PIPELINE MODE)")
            dataset = await self.generate_synthetic_dataset(db, user_id, testset_size)
            
            self.evaluation_state.update({
                "progress": 30,
                "current_step": "Synthetic dataset generated successfully"
            })
            
            # Step 2: Evaluate NAIVE retriever with FULL PIPELINE
            print("📊 Starting NAIVE retriever evaluation...")
            self.evaluation_state.update({
                "status": EvaluationStatus.EVALUATING_NAIVE,
                "progress": 40,
                "current_step": "Starting NAIVE retriever pipeline evaluation"
            })
            
            naive_results = await self.evaluate_full_pipeline(
                db, dataset, RetrieverType.NAIVE, user_id
            )
            
            self.evaluation_state.update({
                "progress": 70,
                "current_step": "NAIVE retriever pipeline evaluation completed"
            })
            
            # Step 3: Evaluate CONTEXTUAL COMPRESSION retriever with FULL PIPELINE
            print("📊 Starting CONTEXTUAL COMPRESSION retriever evaluation...")
            self.evaluation_state.update({
                "status": EvaluationStatus.EVALUATING_COMPRESSION,
                "progress": 80,
                "current_step": "Starting CONTEXTUAL COMPRESSION retriever pipeline evaluation"
            })
            
            compression_results = await self.evaluate_full_pipeline(
                db, dataset, RetrieverType.CONTEXTUAL_COMPRESSION, user_id
            )
            
            # Step 4: Compile final results
            final_results = {
                "evaluation_id": f"ragas_eval_full_pipeline_{int(time.time())}",
                "evaluation_mode": "full_pipeline",
                "user_id": user_id,
                "testset_size": testset_size,
                "dataset_samples": len(dataset),
                "evaluations": {
                    "naive": naive_results,
                    "contextual_compression": compression_results
                },
                "comparison": self._compare_retrievers(naive_results, compression_results),
                "start_time": self.evaluation_state["start_time"],
                "end_time": datetime.now().isoformat()
            }
            
            # STORE FINAL RESULTS IMMEDIATELY
            await self._store_final_results_persistently(final_results)
            
            self.evaluation_state.update({
                "status": EvaluationStatus.COMPLETED,
                "progress": 100,
                "results": final_results,
                "end_time": datetime.now().isoformat(),
                "current_step": "Full pipeline evaluation completed successfully"
            })
            
            print("🎉 RAGAS full pipeline evaluation completed successfully")
            return final_results
            
        except Exception as e:
            error_msg = f"Error in RAGAS full pipeline evaluation: {str(e)}"
            print(f"❌ {error_msg}")
            
            self.evaluation_state.update({
                "status": EvaluationStatus.FAILED,
                "error": error_msg,
                "end_time": datetime.now().isoformat(),
                "current_step": f"Evaluation failed: {error_msg}"
            })
            
            raise e

    async def _store_final_results_persistently(self, final_results: Dict[str, Any]):
        """Store complete evaluation results to prevent total data loss."""
        try:
            import json
            import os
            
            # Create results directory
            results_dir = "ragas_results"
            os.makedirs(results_dir, exist_ok=True)
            
            # Generate filename with evaluation ID
            filename = f"{results_dir}/final_evaluation_{final_results['evaluation_id']}.json"
            
            # Store complete results
            with open(filename, 'w') as f:
                json.dump(final_results, f, indent=2)
            
            print(f"💾 Complete evaluation results stored: {filename}")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to store final results: {e}")
            # This is critical - we should at least try to print results to console
            print("📊 EVALUATION RESULTS (for manual backup):")
            print(json.dumps(final_results, indent=2))

    async def evaluate_retriever(
        self, 
        db: Session, 
        dataset, 
        retriever_type: RetrieverType,
        user_id: int = 4
    ) -> Dict[str, Any]:
        """Evaluate a specific retriever type using RAGAS metrics (LEGACY - retrieval only)."""
        
        print(f"⚠️ Using legacy retrieval-only evaluation for {retriever_type.value}")
        print(f"🔍 Consider using evaluate_full_pipeline() for complete system evaluation")
        
        self.evaluation_state["current_step"] = f"Evaluating {retriever_type.value} retriever"
        
        # Get components
        components = await self.components
        
        # Create retriever
        retriever = create_notion_retriever(db, top_k=5, retriever_type=retriever_type)
        
        # Prepare evaluation dataset
        evaluation_data = []
        dataset_df = dataset.to_pandas()
        
        print(f"🔍 Processing {len(dataset_df)} test samples for {retriever_type.value}")
        
        for idx, row in dataset_df.iterrows():
            question = row["user_input"]
            reference = row["reference"] 
            reference_contexts = row["reference_contexts"]
            
            # Get retrieval results
            try:
                retrieved_docs = await asyncio.to_thread(
                    retriever.invoke,
                    question
                )
                
                retrieved_contexts = [doc.page_content for doc in retrieved_docs]
                
                # For this evaluation, we'll use the reference as the "answer"
                # In a real scenario, you'd run this through your full RAG pipeline
                evaluation_data.append({
                    "question": question,
                    "answer": reference,  # Using reference as answer for evaluation
                    "contexts": retrieved_contexts,
                    "ground_truth": reference,
                    "reference_contexts": reference_contexts
                })
                
            except Exception as e:
                print(f"❌ Error retrieving for question {idx}: {e}")
                # Add empty result for failed retrievals
                evaluation_data.append({
                    "question": question,
                    "answer": reference,
                    "contexts": [],
                    "ground_truth": reference,
                    "reference_contexts": reference_contexts
                })
        
        # Convert to RAGAS dataset format
        eval_dataset = components['ragas_components']['Dataset'].from_list(evaluation_data)
        
        # Define RAGAS metrics
        metrics = [
            components['ragas_components']['ContextPrecision'](),
            components['ragas_components']['LLMContextRecall'](), 
            components['ragas_components']['Faithfulness'](),
            components['ragas_components']['ResponseRelevancy']()
        ]
        
        print(f"📊 Running RAGAS evaluation with {len(metrics)} metrics")
        
        # Run evaluation
        try:
            result = await asyncio.to_thread(
                _run_in_thread_with_new_loop,
                _evaluate_with_ragas_sync,
                components,
                eval_dataset,
                metrics
            )
            
            # Convert result to dict
            result_dict = {
                "retriever_type": retriever_type.value,
                "evaluation_type": "retrieval_only",
                "metrics": {},
                "samples_evaluated": len(evaluation_data),
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract metric scores
            for metric_name, score in result.items():
                if isinstance(score, (int, float)):
                    result_dict["metrics"][metric_name] = float(score)
                else:
                    result_dict["metrics"][metric_name] = str(score)
            
            print(f"✅ {retriever_type.value} evaluation completed")
            return result_dict
            
        except Exception as e:
            print(f"❌ Error during {retriever_type.value} evaluation: {e}")
            return {
                "retriever_type": retriever_type.value,
                "evaluation_type": "retrieval_only",
                "error": str(e),
                "samples_evaluated": len(evaluation_data),
                "timestamp": datetime.now().isoformat()
            }

    def _compare_retrievers(self, naive_results: Dict, compression_results: Dict) -> Dict[str, Any]:
        """Compare the performance of both retrievers."""
        
        comparison = {
            "winner": None,
            "metrics_comparison": {},
            "summary": ""
        }
        
        if "metrics" in naive_results and "metrics" in compression_results:
            naive_metrics = naive_results["metrics"]
            compression_metrics = compression_results["metrics"]
            
            wins = {"naive": 0, "compression": 0}
            
            for metric_name in naive_metrics.keys():
                if metric_name in compression_metrics:
                    naive_score = naive_metrics[metric_name]
                    compression_score = compression_metrics[metric_name]
                    
                    if isinstance(naive_score, (int, float)) and isinstance(compression_score, (int, float)):
                        difference = compression_score - naive_score
                        
                        comparison["metrics_comparison"][metric_name] = {
                            "naive": naive_score,
                            "compression": compression_score,
                            "difference": difference,
                            "winner": "compression" if difference > 0 else "naive" if difference < 0 else "tie"
                        }
                        
                        if difference > 0:
                            wins["compression"] += 1
                        elif difference < 0:
                            wins["naive"] += 1
            
            comparison["winner"] = "compression" if wins["compression"] > wins["naive"] else "naive"
            comparison["summary"] = f"Contextual Compression won {wins['compression']} metrics, Naive won {wins['naive']} metrics"
        
        return comparison
    
    def get_evaluation_status(self) -> Dict[str, Any]:
        """Get current evaluation status."""
        return self.evaluation_state.copy()


# Global service instance
ragas_service = RagasEvaluationService() 