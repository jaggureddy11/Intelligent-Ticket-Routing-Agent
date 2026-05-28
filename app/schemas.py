from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

# --- AGENT ACTION LOG SCHEMAS ---
class AgentActionLogBase(BaseModel):
    agent: str
    action: str
    result: str

class AgentActionLogResponse(AgentActionLogBase):
    id: int
    ticket_id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# --- TICKET SCHEMAS ---
class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Brief summary of the issue")
    description: str = Field(..., min_length=10, description="Full details of the support ticket")

class TicketUpdateStatus(BaseModel):
    status: str = Field(..., pattern="^(New|Assigned|In Progress|Resolved)$")
    resolution_reply: Optional[str] = None

class TicketResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    category: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    created_at: datetime
    sla_deadline: Optional[datetime] = None
    is_sla_breached: bool
    resolution_reply: Optional[str] = None
    action_logs: List[AgentActionLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- EXPERT SCHEMAS ---
class ExpertCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    category: str = Field(..., description="E.g., Network, Software, Hardware, Cloud, General")
    skills: Optional[str] = Field(None, description="Comma-separated skills list")
    is_active: bool = True

class ExpertResponse(BaseModel):
    id: int
    name: str
    category: str
    skills: Optional[str] = None
    is_active: bool
    active_workload: int = 0

    model_config = ConfigDict(from_attributes=True)


# --- ANALYTICS SCHEMAS ---
class AnalyticsDashboard(BaseModel):
    total_tickets: int
    by_category: dict
    by_priority: dict
    by_expert: dict
    sla_compliance_rate: float


# --- AUTH SCHEMAS ---
class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    email: str
    name: str
    expert_id: Optional[int] = None

# --- NOTIFICATION SCHEMAS ---
class PingCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="Custom message to the expert")

class NotificationResponse(BaseModel):
    id: int
    expert_id: int
    sender: str
    message: str
    timestamp: datetime
    is_read: bool

    model_config = ConfigDict(from_attributes=True)
