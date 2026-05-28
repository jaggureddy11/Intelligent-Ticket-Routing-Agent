import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Expert, Ticket, User
from ..schemas import ExpertCreate, ExpertResponse
from ..services.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experts", tags=["Experts"])

@router.get("", response_model=List[ExpertResponse])
def list_experts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists all experts along with their dynamic active workload counts.
    Accessible to all authenticated users.
    """
    experts = db.query(Expert).all()
    response_list = []
    
    for expert in experts:
        # Count active tickets currently assigned to this expert
        active_count = db.query(Ticket).filter(
            Ticket.assignee == expert.name,
            Ticket.status.in_(["Assigned", "In Progress"])
        ).count()
        
        response_list.append(ExpertResponse(
            id=expert.id,
            name=expert.name,
            category=expert.category,
            skills=expert.skills,
            is_active=expert.is_active,
            active_workload=active_count
        ))
        
    return response_list


@router.post("", response_model=ExpertResponse, status_code=status.HTTP_201_CREATED)
def create_expert(
    expert_in: ExpertCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Registers a new expert in the database. Restricted to Administrators."""
    # Check for duplicate name
    existing = db.query(Expert).filter(Expert.name == expert_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Expert with this name already exists")
        
    db_expert = Expert(
        name=expert_in.name,
        category=expert_in.category,
        skills=expert_in.skills,
        is_active=expert_in.is_active
    )
    db.add(db_expert)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during expert creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to create expert."
        )
    db.refresh(db_expert)
    
    return ExpertResponse(
        id=db_expert.id,
        name=db_expert.name,
        category=db_expert.category,
        skills=db_expert.skills,
        is_active=db_expert.is_active,
        active_workload=0
    )


@router.put("/{expert_id}/toggle", response_model=ExpertResponse)
def toggle_expert_active_status(
    expert_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Toggles active/inactive (offline/online) status for an expert. Restricted to Administrators."""
    db_expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not db_expert:
        raise HTTPException(status_code=404, detail="Expert not found")
        
    db_expert.is_active = not db_expert.is_active
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during expert status toggle: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to toggle status."
        )
    db.refresh(db_expert)
    
    active_count = db.query(Ticket).filter(
        Ticket.assignee == db_expert.name,
        Ticket.status.in_(["Assigned", "In Progress"])
    ).count()
    
    return ExpertResponse(
        id=db_expert.id,
        name=db_expert.name,
        category=db_expert.category,
        skills=db_expert.skills,
        is_active=db_expert.is_active,
        active_workload=active_count
    )
