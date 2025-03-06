from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sway Chat API",
    description="Backend API for Sway chat application",
    version="0.1.0",
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Sway Chat API is running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}
