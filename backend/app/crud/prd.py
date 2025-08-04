from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from app.models.prd import PRD
from app.schemas.prd import PRDCreate, PRDUpdate


def create_prd(db: Session, prd: PRDCreate, user_id: int) -> PRD:
    """Create a new PRD for a user"""
    db_prd = PRD(
        title=prd.title,
        content=prd.content,
        user_id=user_id
    )
    db.add(db_prd)
    db.commit()
    db.refresh(db_prd)
    return db_prd


def get_prd(db: Session, prd_id: int, user_id: int) -> Optional[PRD]:
    """Get a specific PRD by ID for a user"""
    return db.query(PRD).filter(
        PRD.id == prd_id, 
        PRD.user_id == user_id
    ).first()


def get_user_prds(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[PRD]:
    """Get all PRDs for a user"""
    return db.query(PRD).filter(
        PRD.user_id == user_id
    ).order_by(desc(PRD.updated_at)).offset(skip).limit(limit).all()


def update_prd(db: Session, prd_id: int, prd_update: PRDUpdate, user_id: int) -> Optional[PRD]:
    """Update a PRD for a user"""
    db_prd = get_prd(db, prd_id, user_id)
    if not db_prd:
        return None
    
    update_data = prd_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prd, field, value)
    
    db.commit()
    db.refresh(db_prd)
    return db_prd


def delete_prd(db: Session, prd_id: int, user_id: int) -> bool:
    """Delete a PRD for a user"""
    db_prd = get_prd(db, prd_id, user_id)
    if not db_prd:
        return False
    
    db.delete(db_prd)
    db.commit()
    return True 