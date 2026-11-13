from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import health, mcp, agent

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous SRE & Incident Response Copilot with LangGraph, Model Context Protocol (MCP), and Human-in-the-Loop Safety.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(mcp.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "status": "online",
        "docs": "/docs",
        "api_v1": "/api/v1"
    }
