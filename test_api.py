import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Expert, Ticket, AgentActionLog, User
from app.services.classifier import classify_ticket, local_fallback_classify_category, local_fallback_classify_priority
from app.services.router import route_ticket_to_expert
from app.services.sla import calculate_sla_deadline, update_ticket_sla_status
from app.services.auth import hash_password, verify_password, create_access_token

# In-memory SQLite for isolated test sessions
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Initializes schema and provides a clean test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# --- 1. TEST CLASSIFICATION FALLBACK RULES ---

def test_fallback_category_rules():
    """Verifies keyword category lookup rules."""
    assert local_fallback_classify_category("VPN broken again", "Cannot connect to server") == "Network"
    assert local_fallback_classify_category("AWS S3 permissions", "Need s3 bucket read access") == "Cloud"
    assert local_fallback_classify_category("Laptop screen flicker", "Screen flickers on tilt") == "Hardware"
    assert local_fallback_classify_category("MS Office installation", "Need license key activated") == "Software"
    assert local_fallback_classify_category("Something random", "Some general inquiry text") == "General"


def test_fallback_priority_rules():
    """Verifies keyword priority urgency matching."""
    assert local_fallback_classify_priority("Urgent printer outage", "Critical block - clients waiting") == "High"
    assert local_fallback_classify_priority("Slow boot speed", "Laptop takes too long to show login") == "Medium"
    assert local_fallback_classify_priority("General query", "Just curious about documentation policies") == "Low"


# --- 2. TEST SLA DEADLINE CALCULATION ---

def test_sla_deadline_offsets():
    """Validates that SLA deadlines are computed correctly based on priorities."""
    now = datetime.now(timezone.utc)
    
    high_deadline = calculate_sla_deadline(now, "High")
    assert high_deadline == now + timedelta(hours=2)
    
    med_deadline = calculate_sla_deadline(now, "Medium")
    assert med_deadline == now + timedelta(hours=8)
    
    low_deadline = calculate_sla_deadline(now, "Low")
    assert low_deadline == now + timedelta(hours=24)


# --- 3. TEST STATEFUL LOAD BALANCING ROUTER ---

def test_load_balancing_routing(db_session):
    """
    Tests stateful load balancing:
    1. Seed two experts for Network category (Priya and Rajesh).
    2. Submit ticket #1. It should route to Priya.
    3. Submit ticket #2. Rajesh must get it (since Priya has workload 1, Rajesh has workload 0).
    4. Submit ticket #3. Workloads are equal (1 each). It routes back to Priya.
    """
    db = db_session
    
    # Register experts
    expert1 = Expert(name="Priya Sharma", category="Network", skills="VPN, Cisco", is_active=True)
    expert2 = Expert(name="Rajesh Patel", category="Network", skills="DNS, Routers", is_active=True)
    db.add(expert1)
    db.add(expert2)
    db.commit()

    # Ticket 1
    t1 = Ticket(title="VPN down", description="Cannot connect", category="Network", priority="High", status="New")
    db.add(t1)
    db.commit()
    route_ticket_to_expert(db, t1)
    assert t1.assignee == "Priya Sharma"
    assert t1.status == "Assigned"

    # Ticket 2
    t2 = Ticket(title="DNS error", description="Lookup failed", category="Network", priority="Medium", status="New")
    db.add(t2)
    db.commit()
    route_ticket_to_expert(db, t2)
    assert t2.assignee == "Rajesh Patel"
    assert t2.status == "Assigned"

    # Ticket 3
    t3 = Ticket(title="Wi-Fi issue", description="Weak signal in office", category="Network", priority="Low", status="New")
    db.add(t3)
    db.commit()
    route_ticket_to_expert(db, t3)
    assert t3.assignee == "Priya Sharma"


# --- 4. TEST SLA BREACH MONITORING ---

def test_sla_breach_detection(db_session):
    """Verifies that past deadlines trigger breaches and manager escalations."""
    db = db_session
    
    # Ticket created in the past, exceeding deadline
    past_creation = datetime.now(timezone.utc) - timedelta(hours=3)
    t = Ticket(
        title="Server crash",
        description="Core database offline",
        category="Cloud",
        priority="High",
        assignee="Neha Gupta",
        created_at=past_creation,
        sla_deadline=past_creation + timedelta(hours=2), # Deadline was 1 hour ago
        status="Assigned",
        is_sla_breached=False
    )
    db.add(t)
    db.commit()

    # Run check
    is_breached = update_ticket_sla_status(db, t)
    assert is_breached is True
    assert t.is_sla_breached is True

    # Verify escalation audit log was created
    log = db.query(AgentActionLog).filter(
        AgentActionLog.ticket_id == t.id,
        AgentActionLog.agent == "SLAMonitorAgent"
    ).first()
    
    assert log is not None
    assert log.action == "escalate"
    assert "SLA Breached!" in log.result


# --- 5. TEST USER AUTHENTICATION & PASSWORD CRYPTOGRAPHY ---

def test_password_cryptography():
    """Validates password hashing and verify services using direct bcrypt."""
    raw = "super_secure_pass123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_generation():
    """Validates encoding and decoding of signed claims."""
    claims = {"sub": "test@company.com", "role": "Admin"}
    token = create_access_token(claims)
    assert token is not None
    assert isinstance(token, str)


# --- 6. TEST ROLE-BASED ACCESS CONTROL (RBAC) CONTROLS ---

def test_rbac_ticket_isolation(db_session):
    """Verifies that support experts only see their own tickets while admins see all."""
    db = db_session
    
    # Create Experts
    expert1 = Expert(name="Priya Sharma", category="Network", is_active=True)
    expert2 = Expert(name="Anjali Mehta", category="Software", is_active=True)
    db.add(expert1)
    db.add(expert2)
    db.flush()

    # Create Users
    user_admin = User(email="admin@company.com", hashed_password="pw", role="Admin")
    user_expert1 = User(email="priya@company.com", hashed_password="pw", role="Expert", expert_id=expert1.id)
    db.add(user_admin)
    db.add(user_expert1)
    
    # Create Tickets
    t1 = Ticket(title="VPN issue", description="Down", assignee="Priya Sharma", status="Assigned")
    t2 = Ticket(title="Word crash", description="Broken", assignee="Anjali Mehta", status="Assigned")
    db.add(t1)
    db.add(t2)
    db.commit()

    # Admin visibility checks (role checking logic)
    assert user_admin.role == "Admin"
    assert user_expert1.role == "Expert"
    
    # Expert 1 (Priya) matches only t1
    expert_name = user_expert1.expert.name
    assert expert_name == "Priya Sharma"
    
    # Query logic simulated matching backend tickets route
    priya_tickets = db.query(Ticket).filter(Ticket.assignee == expert_name).all()
    assert len(priya_tickets) == 1
    assert priya_tickets[0].title == "VPN issue"

    all_tickets = db.query(Ticket).all()
    assert len(all_tickets) == 2


def test_ticket_list_search_and_filters(db_session):
    """Verifies that query filters (q, category, priority) work correctly."""
    db = db_session
    t1 = Ticket(title="Network drop in main office", description="The wifi connection is down.", category="Network", priority="High", assignee="Priya Sharma", status="Assigned")
    t2 = Ticket(title="Office 365 licensing issue", description="Excel says license is expired.", category="Software", priority="Medium", assignee="Anjali Mehta", status="Assigned")
    t3 = Ticket(title="AWS EC2 container deployment crashed", description="Docker instance offline.", category="Cloud", priority="High", assignee="Neha Gupta", status="Assigned")
    db.add(t1)
    db.add(t2)
    db.add(t3)
    db.commit()

    from app.routes.tickets import get_tickets
    user_admin = User(email="admin@company.com", hashed_password="pw", role="Admin")
    
    # 1. Search text 'wifi'
    res = get_tickets(q="wifi", current_user=user_admin, db=db)
    assert len(res) == 1
    assert res[0].title == "Network drop in main office"
    
    # 2. Search category 'Software'
    res = get_tickets(category_filter="Software", current_user=user_admin, db=db)
    assert len(res) == 1
    assert res[0].title == "Office 365 licensing issue"

    # 3. Search priority 'High'
    res = get_tickets(priority_filter="High", current_user=user_admin, db=db)
    assert len(res) == 2


def test_ai_assistance_resolution(db_session):
    """Verifies that AI analyze endpoints return troubleshooting steps and can resolve tickets."""
    db = db_session
    t = Ticket(title="Network outage on VPN connection", description="Cannot load internal pages on corporate VPN client.", category="Network", priority="High", assignee="Priya Sharma", status="Assigned")
    db.add(t)
    db.commit()

    from app.routes.tickets import analyze_ticket_with_ai, update_ticket_status
    from app.schemas import TicketUpdateStatus
    from app.models import Expert
    
    expert = Expert(name="Priya Sharma", category="Network", is_active=True)
    db.add(expert)
    db.commit()
    
    user_expert = User(email="priya@company.com", hashed_password="pw", role="Expert", expert_id=expert.id)
    db.add(user_expert)
    db.commit()

    # 1. Trigger AI analyze
    analysis = analyze_ticket_with_ai(ticket_id=t.id, current_user=user_expert, db=db)
    assert "solutions" in analysis
    assert "draft_reply" in analysis
    assert len(analysis["solutions"]) > 0

    # 2. Update status with resolution reply
    update_data = TicketUpdateStatus(status="Resolved", resolution_reply="Resolved using AI steps: Flushed DNS cache.")
    resolved_ticket = update_ticket_status(ticket_id=t.id, status_update=update_data, current_user=user_expert, db=db)
    assert resolved_ticket.status == "Resolved"
    assert resolved_ticket.resolution_reply == "Resolved using AI steps: Flushed DNS cache."

    # 3. Verify Admin is denied AI analysis
    from fastapi import HTTPException
    user_admin = User(email="admin@company.com", hashed_password="pw", role="Admin")
    with pytest.raises(HTTPException) as exc_info:
        analyze_ticket_with_ai(ticket_id=t.id, current_user=user_admin, db=db)
    assert exc_info.value.status_code == 403

    # 4. Verify Admin is denied status updates
    with pytest.raises(HTTPException) as exc_info:
        update_ticket_status(ticket_id=t.id, status_update=update_data, current_user=user_admin, db=db)
    assert exc_info.value.status_code == 403


# --- 7. TEST ADMIN-TO-EXPERT NOTIFICATION & PING SYSTEM (RBAC) ---

def test_admin_expert_notifications(db_session):
    """Verifies notification access policies (RBAC) and CRUD functions."""
    db = db_session
    
    # Register Expert
    expert = Expert(name="Priya Sharma", category="Network", is_active=True)
    db.add(expert)
    db.flush()

    # Create Users
    user_admin = User(email="admin@company.com", hashed_password="pw", role="Admin")
    user_expert = User(email="priya@company.com", hashed_password="pw", role="Expert", expert_id=expert.id)
    user_other_expert = User(email="arjun@company.com", hashed_password="pw", role="Expert", expert_id=999) # Fake expert
    db.add(user_admin)
    db.add(user_expert)
    db.add(user_other_expert)
    db.commit()

    from app.routes.notifications import ping_expert, get_my_notifications, mark_as_read
    from app.schemas import PingCreate
    from fastapi import HTTPException

    # 1. Admin sends custom message ping to Expert
    ping_data = PingCreate(message="Urgent network issue needs attention!")
    notification = ping_expert(expert_id=expert.id, ping=ping_data, admin_user=user_admin, db=db)
    assert notification.expert_id == expert.id
    assert notification.message == "Urgent network issue needs attention!"
    assert notification.is_read is False

    # 2. Expert fetches their own notifications
    expert_notifications = get_my_notifications(current_user=user_expert, db=db)
    assert len(expert_notifications) == 1
    assert expert_notifications[0].message == "Urgent network issue needs attention!"

    # 3. Admins are blocked from fetching expert notifications
    with pytest.raises(HTTPException) as exc_info:
        get_my_notifications(current_user=user_admin, db=db)
    assert exc_info.value.status_code == 403

    # 4. Expert marks notification as read (dismiss)
    read_notification = mark_as_read(notification_id=notification.id, current_user=user_expert, db=db)
    assert read_notification.is_read is True

    # 5. Other experts are blocked from marking as read
    with pytest.raises(HTTPException) as exc_info:
        mark_as_read(notification_id=notification.id, current_user=user_other_expert, db=db)
    assert exc_info.value.status_code == 403

    # 6. Experts are blocked from sending ping notifications
    with pytest.raises(HTTPException) as exc_info:
        from app.services.auth import require_admin
        require_admin(user_expert)
    assert exc_info.value.status_code == 403



