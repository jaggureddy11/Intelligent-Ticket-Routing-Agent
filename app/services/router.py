import logging
from typing import Tuple
from sqlalchemy.orm import Session
from ..models import Expert, Ticket, AgentActionLog

logger = logging.getLogger(__name__)

def route_ticket_to_expert(db: Session, ticket: Ticket) -> Tuple[str, str]:
    """
    Stateful Routing Agent.
    Finds active experts for the ticket's category, computes their current active workloads
    from the database, and routes the ticket to the expert with the lowest workload.
    """
    logger.info(f"Routing Agent calculating expert for Ticket #{ticket.id} (Category: {ticket.category})")
    
    # 1. Fetch active experts for this category
    experts = db.query(Expert).filter(
        Expert.category == ticket.category,
        Expert.is_active == True
    ).all()
    
    # 2. Fallback to General category if no experts match
    used_fallback = False
    if not experts:
        logger.warning(f"No active experts found for category '{ticket.category}'. Falling back to General.")
        experts = db.query(Expert).filter(
            Expert.category == "General",
            Expert.is_active == True
        ).all()
        used_fallback = True
        
    if not experts:
        # Extreme fallback if even General is empty
        assignee = "Unassigned / Queue"
        routing_log = "No active experts found in category or general pool."
        ticket.assignee = assignee
        ticket.status = "New"
        
        # Log action in database
        action_log = AgentActionLog(
            ticket_id=ticket.id,
            agent="RoutingAgent",
            action="route",
            result=f"Unassigned: {routing_log}"
        )
        db.add(action_log)
        db.commit()
        return assignee, routing_log

    # 3. Calculate current workload for each qualified expert
    # Workload = count of active tickets ('Assigned' or 'In Progress')
    expert_workloads = []
    for expert in experts:
        active_count = db.query(Ticket).filter(
            Ticket.assignee == expert.name,
            Ticket.status.in_(["Assigned", "In Progress"])
        ).count()
        expert_workloads.append((expert, active_count))
        logger.info(f"Expert: {expert.name} | Specialization: {expert.category} | Current Workload: {active_count}")

    # 4. Route to the expert with the lowest workload
    # Sorting by workload count (first element in key lambda)
    best_expert, min_load = min(expert_workloads, key=lambda x: x[1])
    assignee = best_expert.name
    
    # Update ticket parameters
    ticket.assignee = assignee
    ticket.status = "Assigned"
    
    # Construct result message
    routing_log = f"Routed to {assignee} (Category: {best_expert.category}, Load: {min_load} active tickets)"
    if used_fallback:
        routing_log += " [Fallback to General pool]"
        
    # 5. Log action in database for audit trail
    action_log = AgentActionLog(
        ticket_id=ticket.id,
        agent="RoutingAgent",
        action="route",
        result=routing_log
    )
    db.add(action_log)
    db.commit()
    
    logger.info(f"Ticket #{ticket.id} routed to {assignee} successfully.")
    return assignee, routing_log
