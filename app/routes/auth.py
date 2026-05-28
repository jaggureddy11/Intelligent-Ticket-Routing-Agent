from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Expert
from ..schemas import Token, UserLogin
from ..services.auth import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 password flow login endpoint.
    Accepts form-data (username and password).
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Resolve display name
    name = "System Administrator"
    if user.role == "Expert" and user.expert_id:
        expert = db.query(Expert).filter(Expert.id == user.expert_id).first()
        if expert:
            name = expert.name
            
    access_token = create_access_token(data={"sub": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        email=user.email,
        name=name,
        expert_id=user.expert_id
    )


@router.post("/login-json", response_model=Token)
def login_json(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    JSON-based login endpoint.
    Accepts JSON body (email and password). Used by the frontend dashboard.
    """
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Resolve display name
    name = "System Administrator"
    if user.role == "Expert" and user.expert_id:
        expert = db.query(Expert).filter(Expert.id == user.expert_id).first()
        if expert:
            name = expert.name
            
    access_token = create_access_token(data={"sub": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        email=user.email,
        name=name,
        expert_id=user.expert_id
    )
