import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine, Base
from app.routes import auth, tickets, experts, analytics, notifications

# Initialize logging configuration before doing anything else
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create database tables automatically if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Intelligent IT Support Ticket Routing Agent",
    description="GenAI-Powered multi-agent ticket classification, prioritization, and load-balancing routing backend service.",
    version="1.0.0"
)

# Custom Middleware for Security Headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS dynamically based on configuration settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error encountered: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "A database transaction error occurred. Please try again later."}
    )

@app.exception_handler(Exception)
def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled system error occurred: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."}
    )

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(experts.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")

@app.get("/api/status")
def get_huggingface_status():
    from app.config import settings
    token_configured = (
        settings.HF_TOKEN is not None 
        and settings.HF_TOKEN.strip() != "" 
        and "your_huggingface_access_token" not in settings.HF_TOKEN
    )
    return {"hf_enabled": token_configured}

# Mount Static Files to serve the Dashboard SPA
# Serves app/static/index.html directly at the root URL '/'
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

if __name__ == "__main__":
    # Load port from settings configuration
    port = int(settings.PORT)
    print(f"🚀 Server launching at http://localhost:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
