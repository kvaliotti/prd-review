"""
RAGAS Evaluation API Router.

Provides endpoints for:
- Starting RAGAS evaluation 
- Checking evaluation status
- Getting evaluation results
"""

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.connection import get_db
from app.core.security import verify_token
from app.models.user import User
from app.crud import user as user_crud
from app.services.ragas_evaluation_service import ragas_service, EvaluationStatus


router = APIRouter(prefix="/ragas-evaluation", tags=["ragas-evaluation"])

# Authentication setup for router
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=401,
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


class EvaluationRequest(BaseModel):
    """Request model for starting RAGAS evaluation."""
    user_id: Optional[int] = None  # If not provided, uses current user
    testset_size: int = 10
    

class EvaluationResponse(BaseModel):
    """Response model for evaluation status."""
    status: str
    progress: int
    current_step: str
    message: str


class EvaluationResultsResponse(BaseModel):
    """Response model for evaluation results."""
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


async def run_evaluation_background(db: Session, user_id: int, testset_size: int):
    """Background task to run RAGAS evaluation."""
    try:
        await ragas_service.run_full_evaluation(db, user_id, testset_size)
    except Exception as e:
        print(f"Background evaluation failed: {e}")


@router.post("/start", response_model=EvaluationResponse)
async def start_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start RAGAS evaluation process."""
    
    # Check if evaluation is already running
    current_status = ragas_service.get_evaluation_status()
    if current_status["status"] in [
        EvaluationStatus.GENERATING_DATASET,
        EvaluationStatus.EVALUATING_NAIVE, 
        EvaluationStatus.EVALUATING_COMPRESSION
    ]:
        raise HTTPException(
            status_code=409, 
            detail="Evaluation is already running"
        )
    
    # Use specified user_id or current user
    target_user_id = request.user_id or current_user.id
    
    # Validate user_id (basic check)
    if target_user_id != current_user.id and target_user_id != 4:
        # For demo purposes, only allow current user or user 4
        raise HTTPException(
            status_code=403,
            detail="You can only run evaluation for your own data or demo user (ID: 4)"
        )
    
    # Reset evaluation state
    ragas_service.evaluation_state = {
        "status": EvaluationStatus.PENDING,
        "progress": 0,
        "current_step": "",
        "results": {},
        "error": None,
        "start_time": None,
        "end_time": None
    }
    
    # Start evaluation in background
    background_tasks.add_task(
        run_evaluation_background,
        db,
        target_user_id,
        request.testset_size
    )
    
    return EvaluationResponse(
        status=EvaluationStatus.PENDING,
        progress=0,
        current_step="Evaluation queued",
        message=f"Started RAGAS evaluation for user {target_user_id} with {request.testset_size} test samples"
    )


@router.get("/status", response_model=EvaluationResponse)
async def get_evaluation_status(
    current_user: User = Depends(get_current_user)
):
    """Get current evaluation status."""
    
    status = ragas_service.get_evaluation_status()
    
    # Map status to user-friendly message
    status_messages = {
        EvaluationStatus.PENDING: "Evaluation is queued",
        EvaluationStatus.GENERATING_DATASET: "Generating synthetic dataset with RAGAS",
        EvaluationStatus.EVALUATING_NAIVE: "Evaluating Naive retriever",
        EvaluationStatus.EVALUATING_COMPRESSION: "Evaluating Contextual Compression retriever", 
        EvaluationStatus.COMPLETED: "Evaluation completed successfully",
        EvaluationStatus.FAILED: f"Evaluation failed: {status.get('error', 'Unknown error')}"
    }
    
    return EvaluationResponse(
        status=status["status"],
        progress=status["progress"],
        current_step=status["current_step"],
        message=status_messages.get(status["status"], "Unknown status")
    )


@router.get("/results", response_model=EvaluationResultsResponse)
async def get_evaluation_results(
    current_user: User = Depends(get_current_user)
):
    """Get evaluation results if completed."""
    
    status = ragas_service.get_evaluation_status()
    
    if status["status"] == EvaluationStatus.COMPLETED:
        return EvaluationResultsResponse(
            status="completed",
            results=status["results"]
        )
    elif status["status"] == EvaluationStatus.FAILED:
        return EvaluationResultsResponse(
            status="failed",
            error=status.get("error", "Unknown error")
        )
    else:
        return EvaluationResultsResponse(
            status=status["status"],
            results=None
        )


@router.delete("/reset")
async def reset_evaluation(
    current_user: User = Depends(get_current_user)
):
    """Reset evaluation state (admin function)."""
    
    ragas_service.evaluation_state = {
        "status": EvaluationStatus.PENDING,
        "progress": 0,
        "current_step": "",
        "results": {},
        "error": None,
        "start_time": None,
        "end_time": None
    }
    
    return {"message": "Evaluation state reset successfully"}


@router.get("/test")
async def test_ragas_service():
    """Test endpoint to verify RAGAS service is working."""
    return {
        "status": "RAGAS Evaluation service is running",
        "version": "1.0",
        "available_metrics": [
            "ContextPrecision",
            "LLMContextRecall", 
            "Faithfulness",
            "FactualCorrectness",
            "ResponseRelevancy",
            "ContextEntityRecall",
            "NoiseSensitivity"
        ]
    } 