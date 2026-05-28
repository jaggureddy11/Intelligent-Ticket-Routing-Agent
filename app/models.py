from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(50), default="New") # New, Assigned, In Progress, Resolved
    category = Column(String(100), nullable=True) # Network, Software, Hardware, Cloud, General
    priority = Column(String(50), nullable=True) # High, Medium, Low
    assignee = Column(String(100), nullable=True) # Expert's name
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sla_deadline = Column(DateTime, nullable=True)
    is_sla_breached = Column(Boolean, default=False)
    resolution_reply = Column(Text, nullable=True)

    # Relationships
    action_logs = relationship("AgentActionLog", back_populates="ticket", cascade="all, delete-orphan")

class Expert(Base):
    __tablename__ = "experts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(100), nullable=False) # Network, Software, Hardware, Cloud, General
    skills = Column(String(255), nullable=True) # Comma-separated list of skills
    is_active = Column(Boolean, default=True)

    # Relation to login user details
    user = relationship("User", back_populates="expert", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="expert", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="Expert") # Admin, Expert
    expert_id = Column(Integer, ForeignKey("experts.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    expert = relationship("Expert", back_populates="user")

class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    agent = Column(String(100), nullable=False) # ClassificationAgent, PrioritizationAgent, RoutingAgent, SLAMonitorAgent
    action = Column(String(255), nullable=False)
    result = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relation to parent
    ticket = relationship("Ticket", back_populates="action_logs")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    expert_id = Column(Integer, ForeignKey("experts.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String(100), default="Admin")
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = Column(Boolean, default=False)

    # Relationship
    expert = relationship("Expert", back_populates="notifications")
