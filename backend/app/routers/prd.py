from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models import User
from app.core.security import verify_token
from app.crud import user as user_crud
from app.crud import prd as prd_crud
from app.schemas.prd import PRD, PRDCreate, PRDUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/prds", tags=["prds"])

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


@router.post("/", response_model=PRD, status_code=status.HTTP_201_CREATED)
async def create_prd(
    prd: PRDCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new PRD"""
    try:
        logger.info(f"Creating new PRD for user {current_user.id}")
        db_prd = prd_crud.create_prd(db=db, prd=prd, user_id=current_user.id)
        logger.info(f"Created PRD {db_prd.id} for user {current_user.id}")
        return db_prd
    except Exception as e:
        logger.error(f"Failed to create PRD for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create PRD"
        )


@router.get("/", response_model=List[PRD])
async def get_prds(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all PRDs for the current user"""
    try:
        logger.info(f"Getting PRDs for user {current_user.id}")
        prds = prd_crud.get_user_prds(db=db, user_id=current_user.id, skip=skip, limit=limit)
        logger.info(f"Retrieved {len(prds)} PRDs for user {current_user.id}")
        return prds
    except Exception as e:
        logger.error(f"Failed to get PRDs for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve PRDs"
        )


@router.get("/{prd_id}", response_model=PRD)
async def get_prd(
    prd_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific PRD by ID"""
    try:
        logger.info(f"Getting PRD {prd_id} for user {current_user.id}")
        db_prd = prd_crud.get_prd(db=db, prd_id=prd_id, user_id=current_user.id)
        if not db_prd:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PRD not found"
            )
        return db_prd
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get PRD {prd_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve PRD"
        )


@router.put("/{prd_id}", response_model=PRD)
async def update_prd(
    prd_id: int,
    prd_update: PRDUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a PRD"""
    try:
        logger.info(f"Updating PRD {prd_id} for user {current_user.id}")
        db_prd = prd_crud.update_prd(
            db=db, 
            prd_id=prd_id, 
            prd_update=prd_update, 
            user_id=current_user.id
        )
        if not db_prd:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PRD not found"
            )
        logger.info(f"Updated PRD {prd_id} for user {current_user.id}")
        return db_prd
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update PRD {prd_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update PRD"
        )


@router.delete("/{prd_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prd(
    prd_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a PRD"""
    try:
        logger.info(f"Deleting PRD {prd_id} for user {current_user.id}")
        success = prd_crud.delete_prd(db=db, prd_id=prd_id, user_id=current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PRD not found"
            )
        logger.info(f"Deleted PRD {prd_id} for user {current_user.id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete PRD {prd_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete PRD"
        ) 