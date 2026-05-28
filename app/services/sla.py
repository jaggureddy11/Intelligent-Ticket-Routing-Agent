import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from ..models import Ticket, AgentActionLog

logger = logging.getLogger(__name__)

# SLA Thresholds in Hours
SLA_THRESHOLDS = {
    "High": 2,     # 2 Hours
    "Medium": 8,   # 8 Hours
    "Low": 24      # 24 Hours
}

def calculate_sla_deadline(created_at: datetime, priority: str) -> datetime:
    """Computes the exact timezone-aware deadline based on priority."""
    hours = SLA_THRESHOLDS.get(priority, 24)
    # Ensure created_at is timezone-aware
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(hours=hours)


def update_ticket_sla_status(db: Session, ticket: Ticket) -> bool:
    """
    Checks the current ticket's SLA status.
    If the deadline is passed and the ticket is unresolved, sets is_sla_breached = True
    and logs an escalation action if not already breached.
    """
    if ticket.status == "Resolved" or not ticket.sla_deadline:
        return ticket.is_sla_breached

    # Ensure SLA deadline is timezone-aware
    deadline = ticket.sla_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    
    if now > deadline and not ticket.is_sla_breached:
        # Mark as breached
        ticket.is_sla_breached = True
        
        # Log escalation warning
        escalation_msg = f"SLA Breached! Ticket outstanding for {round((now - ticket.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600.0, 2)} hours. Escalated to {ticket.assignee}'s manager."
        action_log = AgentActionLog(
            ticket_id=ticket.id,
            agent="SLAMonitorAgent",
            action="escalate",
            result=escalation_msg
        )
        db.add(action_log)
        db.commit()
        logger.warning(f"Ticket #{ticket.id} SLA breached and escalated.")
        return True
        
    return ticket.is_sla_breached


def check_all_tickets_sla(db: Session) -> int:
    """
    Scans all unresolved tickets and updates their SLA breach status.
    Returns: Count of tickets that are breached.
    """
    unresolved_tickets = db.query(Ticket).filter(Ticket.status != "Resolved").all()
    breach_count = 0
    for ticket in unresolved_tickets:
        was_updated = update_ticket_sla_status(db, ticket)
        if ticket.is_sla_breached:
            breach_count += 1
            
    return breach_count
