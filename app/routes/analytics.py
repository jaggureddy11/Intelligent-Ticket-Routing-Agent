from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Ticket, Expert, User
from ..schemas import AnalyticsDashboard
from ..services.auth import require_admin
from ..services.sla import check_all_tickets_sla

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("", response_model=AnalyticsDashboard)
def get_analytics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Computes real-time system metrics, category distributions,
    workloads, and SLA compliance rates. Restricted to Administrators.
    """
    # 1. Sweep SLA state to ensure accuracy
    check_all_tickets_sla(db)
    
    total_tickets = db.query(Ticket).count()
    
    # If no tickets, return default empty statistics
    if total_tickets == 0:
        return AnalyticsDashboard(
            total_tickets=0,
            by_category={},
            by_priority={},
            by_expert={},
            sla_compliance_rate=100.0
        )
        
    # 2. Group by Category
    category_data = db.query(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category).all()
    by_category = {cat: count for cat, count in category_data if cat}
    
    # 3. Group by Priority
    priority_data = db.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    by_priority = {pri: count for pri, count in priority_data if pri}
    
    # 4. Expert Workloads (Assignee with active tickets count)
    expert_data = db.query(Ticket.assignee, func.count(Ticket.id)).filter(
        Ticket.status.in_(["Assigned", "In Progress"])
    ).group_by(Ticket.assignee).all()
    by_expert = {exp: count for exp, count in expert_data if exp}
    
    # Ensure all configured experts are in by_expert (even if 0 workload)
    all_experts = db.query(Expert.name).filter(Expert.is_active == True).all()
    for exp_row in all_experts:
        exp_name = exp_row[0]
        if exp_name not in by_expert:
            by_expert[exp_name] = 0

    # 5. SLA Compliance Rate
    breached_count = db.query(Ticket).filter(Ticket.is_sla_breached == True).count()
    sla_compliance_rate = round(100.0 * (1.0 - (breached_count / total_tickets)), 2)
    
    return AnalyticsDashboard(
        total_tickets=total_tickets,
        by_category=by_category,
        by_priority=by_priority,
        by_expert=by_expert,
        sla_compliance_rate=sla_compliance_rate
    )
