import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Ticket, AgentActionLog, User
from ..schemas import TicketCreate, TicketResponse, TicketUpdateStatus
from ..services.auth import get_current_user
from ..services.classifier import classify_ticket
from ..services.router import route_ticket_to_expert
from ..services.sla import calculate_sla_deadline, check_all_tickets_sla, update_ticket_sla_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

@router.get("", response_model=List[TicketResponse])
def get_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    q: Optional[str] = Query(None, description="Search keyword in title, description, or assignee"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves tickets with optional search and filters.
    Admin: Returns all tickets matching queries.
    Expert: Returns only tickets assigned to them matching queries.
    Triggers an on-demand SLA sweep to update breach indicators before returning list.
    """
    check_all_tickets_sla(db)
    
    query = db.query(Ticket)
    if status_filter and isinstance(status_filter, str):
        query = query.filter(Ticket.status == status_filter)
    if category_filter and isinstance(category_filter, str):
        query = query.filter(Ticket.category == category_filter)
    if priority_filter and isinstance(priority_filter, str):
        query = query.filter(Ticket.priority == priority_filter)
    if q and isinstance(q, str):
        search_pattern = f"%{q}%"
        query = query.filter(
            Ticket.title.ilike(search_pattern) | 
            Ticket.description.ilike(search_pattern) | 
            Ticket.assignee.ilike(search_pattern)
        )
        
    # Enforce Role-Based Visibility
    if current_user.role == "Expert":
        expert_name = current_user.expert.name if current_user.expert else ""
        query = query.filter(Ticket.assignee == expert_name)
        
    return query.order_by(Ticket.id.desc()).all()


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_in: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a ticket and executes the multi-agent classification, prioritization,
    SLA mapping, and load-balancing routing sequential pipeline.
    """
    # 1. Instantiate the ticket in Database
    now = datetime.now(timezone.utc)
    new_ticket = Ticket(
        title=ticket_in.title,
        description=ticket_in.description,
        status="New",
        created_at=now,
        is_sla_breached=False
    )
    db.add(new_ticket)
    db.flush()  # Generates the ticket ID

    # 2. Agent 1 & 2: Classification and Prioritization
    classification = classify_ticket(ticket_in.title, ticket_in.description)
    
    new_ticket.category = classification["category"]
    new_ticket.priority = classification["priority"]
    new_ticket.sla_deadline = calculate_sla_deadline(now, classification["priority"])
    
    # Save classification action logs
    cat_log = AgentActionLog(
        ticket_id=new_ticket.id,
        agent="ClassificationAgent",
        action="classify",
        result=f"Category: {classification['category']} | Source: {classification['category_source']}"
    )
    pri_log = AgentActionLog(
        ticket_id=new_ticket.id,
        agent="PrioritizationAgent",
        action="prioritize",
        result=f"Priority: {classification['priority']} | Source: {classification['priority_source']}"
    )
    db.add(cat_log)
    db.add(pri_log)
    
    # 3. Agent 3: Routing
    route_ticket_to_expert(db, new_ticket)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during ticket creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to create ticket."
        )
    db.refresh(new_ticket)
    return new_ticket


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket_details(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves a single ticket's full details and audit logs, checking permissions and updating SLA."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # Enforce Read Permissions
    if current_user.role == "Expert":
        expert_name = current_user.expert.name if current_user.expert else ""
        if ticket.assignee != expert_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view tickets assigned to you."
            )
            
    update_ticket_sla_status(db, ticket)
    return ticket


@router.put("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    status_update: TicketUpdateStatus,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates a ticket's status. Experts can only resolve tickets assigned to them."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # Enforce Write/Update Permissions - ONLY the assigned Expert can modify status
    if current_user.role != "Expert":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only support experts can modify ticket status."
        )
        
    expert_name = current_user.expert.name if current_user.expert else ""
    if ticket.assignee != expert_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only update tickets assigned to you."
        )
            
    old_status = ticket.status
    new_status = status_update.status
    
    if old_status == new_status and ticket.resolution_reply == status_update.resolution_reply:
        return ticket
        
    ticket.status = new_status
    if status_update.resolution_reply:
        ticket.resolution_reply = status_update.resolution_reply
        
    # Add audit log for status change
    log_msg = f"Status changed from '{old_status}' to '{new_status}' by {current_user.email}"
    if status_update.resolution_reply:
        log_msg += f" | AI Resolution applied."
        
    action_log = AgentActionLog(
        ticket_id=ticket.id,
        agent="System",
        action="update_status",
        result=log_msg
    )
    db.add(action_log)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during ticket status update: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to update ticket status."
        )
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/analyze-ai", response_model=dict)
def analyze_ticket_with_ai(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Expert-only AI assistance endpoint.
    Queries the multi-agent AI pipeline or local fallbacks to retrieve troubleshooting steps and draft response message.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # Security guard: only the assigned Expert can run AI analysis
    if current_user.role != "Expert":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only support experts can run AI analysis."
        )
        
    expert_name = current_user.expert.name if current_user.expert else ""
    if ticket.assignee != expert_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only analyze tickets assigned to you."
        )
            
    # Trigger resolution services
    from ..services.classifier import analyze_ticket_resolution
    analysis = analyze_ticket_resolution(ticket.title, ticket.description, ticket.category)
    
    # Save log of AI assistance run
    action_log = AgentActionLog(
        ticket_id=ticket.id,
        agent="AIAssistantAgent",
        action="analyze_resolution",
        result=f"Generated troubleshooting list & draft response. Source: {analysis['source']}"
    )
    db.add(action_log)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during AI resolution logging: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to log AI analysis request."
        )
    
    return analysis
