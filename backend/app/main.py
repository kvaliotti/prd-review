import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
import logging

# Core imports
from app.core.config import settings

# Initialize LangSmith tracing if configured
if settings.langsmith_tracing and settings.langsmith_tracing.lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.langsmith_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    
    print(f"🔍 LangSmith tracing enabled for project: {settings.langsmith_project}")
else:
    print("ℹ️  LangSmith tracing disabled")

from app.core.logging import configure_logging, LoggingMiddleware, auth_logger, chat_logger, get_logger
from app.core.rate_limiter import rate_limit_middleware, setup_redis_rate_limiter, limiter, rate_limit_handler
from app.core.monitoring import (
    MetricsMiddleware, get_metrics, record_auth_attempt, 
    record_llm_request, update_health_status, DatabaseMetricsCollector
)

# Database and models
from app.database.connection import get_db, engine, create_tables, check_database_health, get_db_stats
from app.models import User, Chat, Message

# Schemas and CRUD
from app.schemas import (
    UserCreate, UserLogin, Token, User as UserSchema,
    ChatCreate, ChatList, MessageCreate, ChatResponse
)
from app.crud import user as user_crud, chat as chat_crud

# Security and services
from app.core.security import (
    verify_token, create_access_token, create_refresh_token
)
from app.services.llm_agent import EnhancedChatAgent

# Import routers
from app.routers import notion, prd, prd_analysis, ragas_evaluation

# Configure logging
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Chat App API", version=settings.app_version)
    
    # Create database tables
    create_tables()
    
    # Setup Redis rate limiter if enabled
    if settings.rate_limit_enabled and settings.redis_url:
        setup_redis_rate_limiter(settings.redis_url)
    
    # Initialize health status
    update_health_status("database", check_database_health())
    update_health_status("redis", True)  # Will be updated by rate limiter
    update_health_status("openai", True)  # Will be updated by LLM agent
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down Chat App API")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    **settings.get_cors_config()
)

# Add custom middleware
if settings.metrics_enabled:
    app.add_middleware(MetricsMiddleware)

app.add_middleware(LoggingMiddleware)

# Add rate limiting middleware
if settings.rate_limit_enabled:
    app.middleware("http")(rate_limit_middleware)

# Initialize security and chat agent
security = HTTPBearer()
chat_agent = EnhancedChatAgent()


# Authentication dependency
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
        
        auth_logger.debug("User authenticated", user_id=user.id, email=user.email)
        return user
        
    except Exception as e:
        auth_logger.warning("Authentication failed", error=str(e))
        record_auth_attempt(False)
        raise


# Auth endpoints
@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Validate password length
    if len(user.password) < settings.password_min_length:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.password_min_length} characters long"
        )
    
    # Check if user already exists
    if user_crud.get_user_by_email(db, email=user.email):
        auth_logger.warning("Registration attempt with existing email", email=user.email)
        record_auth_attempt(False)
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create user
    db_user = user_crud.create_user(db, user)
    if not db_user:
        raise HTTPException(
            status_code=400,
            detail="Failed to create user"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    auth_logger.info("User registered successfully", user_id=db_user.id, email=db_user.email)
    record_auth_attempt(True)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/auth/login", response_model=Token)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    authenticated_user = user_crud.authenticate_user(db, user.email, user.password)
    if not authenticated_user:
        auth_logger.warning("Login failed", email=user.email)
        record_auth_attempt(False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    auth_logger.info("User logged in", user_id=authenticated_user.id, email=authenticated_user.email)
    record_auth_attempt(True)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.get("/auth/me", response_model=UserSchema)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


# Chat endpoints
@app.get("/chats", response_model=List[ChatList])
async def get_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chats for current user"""
    return chat_crud.get_user_chats(db, current_user.id)


@app.post("/chats", response_model=ChatList)
async def create_chat(
    chat: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat"""
    # Validate title length
    if len(chat.title) > settings.chat_title_max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Chat title must be less than {settings.chat_title_max_length} characters"
        )
    
    db_chat = chat_crud.create_chat(db, chat, current_user.id)
    chat_logger.info("Chat created", chat_id=db_chat.id, user_id=current_user.id, title=db_chat.title)
    
    return {
        "id": db_chat.id,
        "title": db_chat.title,
        "created_at": db_chat.created_at,
        "updated_at": db_chat.updated_at,
        "message_count": 0
    }


@app.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a chat"""
    messages = chat_crud.get_chat_messages(db, chat_id, current_user.id)
    return messages


@app.post("/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: int,
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message and get AI response"""
    # Validate message length
    if len(message.content) > settings.max_message_length:
        raise HTTPException(
            status_code=400,
            detail=f"Message must be less than {settings.max_message_length} characters"
        )
    
    # Verify chat belongs to user
    chat = chat_crud.get_chat_by_id(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Save user message
    user_message = chat_crud.create_message(db, message, chat_id)
    chat_logger.info("Message sent", chat_id=chat_id, user_id=current_user.id, message_id=user_message.id)
    
    # Get chat history
    message_history = chat_crud.get_chat_messages(db, chat_id, current_user.id)
    
    # Auto-generate title if this is the first user message
    if len([m for m in message_history if m.role == "user"]) == 1:
        try:
            new_title = chat_agent.generate_chat_title(message.content)
            chat_crud.update_chat_title(db, chat_id, current_user.id, new_title)
            chat_logger.info("Chat title auto-generated", chat_id=chat_id, title=new_title)
        except Exception as e:
            chat_logger.warning("Failed to auto-generate chat title", chat_id=chat_id, error=str(e))
    
    try:
        # Create user context for enhanced responses
        user_context = {
            "user_email": current_user.email,
            "chat_id": chat_id,
            "chat_title": chat.title
        }
        
        # Generate AI response with timing
        start_time = time.time()
        ai_response = chat_agent.generate_response(
            message_history[:-1],
            message.content,
            user_context
        )
        duration = time.time() - start_time
        
        # Save AI response
        ai_message = MessageCreate(content=ai_response, role="assistant")
        ai_message_db = chat_crud.create_message(db, ai_message, chat_id)
        
        # Record metrics
        record_llm_request(duration, True)
        chat_logger.info(
            "AI response generated", 
            chat_id=chat_id, 
            user_id=current_user.id,
            ai_message_id=ai_message_db.id,
            duration=duration
        )
        
        return {"message": ai_response}
    
    except Exception as e:
        chat_logger.error("Error generating AI response", chat_id=chat_id, error=str(e))
        record_llm_request(0, False)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate AI response"
        )


@app.post("/chats/{chat_id}/generate-title")
async def generate_chat_title(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a new title for an existing chat based on its content"""
    chat = chat_crud.get_chat_by_id(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = chat_crud.get_chat_messages(db, chat_id, current_user.id)
    user_messages = [m for m in messages if m.role == "user"]
    
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user messages found to generate title from")
    
    try:
        first_message = user_messages[0].content
        new_title = chat_agent.generate_chat_title(first_message)
        
        updated_chat = chat_crud.update_chat_title(db, chat_id, current_user.id, new_title)
        if not updated_chat:
            raise HTTPException(status_code=404, detail="Failed to update chat title")
        
        chat_logger.info("Chat title regenerated", chat_id=chat_id, title=new_title)
        return {"title": new_title}
    
    except Exception as e:
        chat_logger.error("Error regenerating chat title", chat_id=chat_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate chat title")


@app.get("/chats/{chat_id}/context")
async def get_chat_context(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get conversation context and analytics for a chat"""
    chat = chat_crud.get_chat_by_id(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = chat_crud.get_chat_messages(db, chat_id, current_user.id)
    
    try:
        context = chat_agent.analyze_conversation_context(messages)
        return {
            "chat_id": chat_id,
            "title": chat.title,
            "context": context
        }
    
    except Exception as e:
        chat_logger.error("Error analyzing chat context", chat_id=chat_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to analyze chat context")


# Health and monitoring endpoints
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.app_version,
        "environment": settings.environment,
        "services": {}
    }
    
    # Check database
    db_healthy = check_database_health()
    health_status["services"]["database"] = {
        "status": "healthy" if db_healthy else "unhealthy",
        "stats": get_db_stats()
    }
    update_health_status("database", db_healthy)
    
    # Check OpenAI (simple check)
    try:
        # This is a lightweight check - we're not actually calling the API
        openai_healthy = bool(settings.openai_api_key)
        health_status["services"]["openai"] = {
            "status": "configured" if openai_healthy else "not_configured"
        }
        update_health_status("openai", openai_healthy)
    except Exception:
        health_status["services"]["openai"] = {"status": "error"}
        update_health_status("openai", False)
    
    # Check Redis (if enabled)
    if settings.rate_limit_enabled:
        try:
            # This would be implemented with an actual Redis ping
            health_status["services"]["redis"] = {"status": "configured"}
            update_health_status("redis", True)
        except Exception:
            health_status["services"]["redis"] = {"status": "error"}
            update_health_status("redis", False)
    
    # Overall status
    service_statuses = [
        health_status["services"]["database"]["status"] == "healthy",
        health_status["services"]["openai"]["status"] == "configured"
    ]
    
    if all(service_statuses):
        health_status["status"] = "healthy"
        status_code = 200
    else:
        health_status["status"] = "unhealthy"
        status_code = 503
    
    return Response(
        content=str(health_status),
        status_code=status_code,
        media_type="application/json"
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return await get_metrics()


@app.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get application statistics (admin endpoint)"""
    try:
        # Collect database metrics
        await DatabaseMetricsCollector.collect_from_db(db)
        
        stats = {
            "database": get_db_stats(),
            "application": {
                "version": settings.app_version,
                "environment": settings.environment,
                "features": {
                    "rate_limiting": settings.rate_limit_enabled,
                    "metrics": settings.metrics_enabled,
                    "redis": bool(settings.redis_url)
                }
            }
        }
        
        return stats
    except Exception as e:
        logger.error("Error collecting stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to collect stats")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Enhanced Chat App API",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs_url": "/docs" if settings.is_development else None,
        "health_url": "/health",
        "metrics_url": "/metrics" if settings.metrics_enabled else None
    }


# Include routers with authentication dependency
app.include_router(
    notion.router,
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    prd.router,
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    prd_analysis.router
    # No global auth dependency - handles EventSource authentication manually per endpoint
)

app.include_router(
    ragas_evaluation.router
    # No global auth dependency - handled per endpoint for EventSource compatibility
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.host, 
        port=settings.port,
        log_level=settings.log_level.lower()
    ) 