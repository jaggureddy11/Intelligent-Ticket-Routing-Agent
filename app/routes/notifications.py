import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Notification, Expert, User
from ..schemas import PingCreate, NotificationResponse
from ..services.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/ping/{expert_id}", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def ping_expert(
    expert_id: int,
    ping: PingCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Allows Administrators to send a custom message ping to a specific Support Expert.
    Strictly restricted to Admins.
    """
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")
        
    db_notification = Notification(
        expert_id=expert_id,
        sender="Admin",
        message=ping.message,
        is_read=False
    )
    db.add(db_notification)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during expert ping notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to send notification."
        )
    db.refresh(db_notification)
    return db_notification


@router.get("", response_model=List[NotificationResponse])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows Experts to view their own incoming notifications/pings.
    Blocked for Admins.
    """
    if current_user.role != "Expert" or current_user.expert_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Expert privileges required"
        )
        
    notifications = db.query(Notification).filter(
        Notification.expert_id == current_user.expert_id
    ).order_by(Notification.timestamp.desc()).all()
    
    return notifications


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows Experts to mark their own notifications as read (dismissing them).
    Blocked for Admins.
    """
    if current_user.role != "Expert" or current_user.expert_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Expert privileges required"
        )
        
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    if notification.expert_id != current_user.expert_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Notification belongs to another expert"
        )
        
    notification.is_read = True
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during notification dismiss: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database transaction error occurred. Failed to mark notification as read."
        )
    db.refresh(notification)
    return notification
