"""AI Task Management Agent - FastAPI Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from src.api import router
from src.database.connection import async_engine, init_db
from src.skills.registry import get_registry


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print("Starting AI Task Management Agent...")

    # Initialize database
    print("Initializing database...")
    await init_db()
    print("Database initialized.")

    # Initialize skill registry
    print("Loading skills...")
    registry = await get_registry()
    skill_count = len(registry.list_skills())
    print(f"Loaded {skill_count} skills.")

    print("AI Task Management Agent ready!")

    yield

    # Shutdown
    print("Shutting down AI Task Management Agent...")
    await async_engine.dispose()
    print("Shutdown complete.")


app = FastAPI(
    title="AI Task Management Agent",
    description="An intelligent AI-powered task management assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "name": "AI Task Management Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/api/v1",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
