from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import health, stats, mood, discovery, patterns, milestones, sessions, reco, sim, compare

# Create FastAPI app
app = FastAPI(
    title="Spotify Insights API",
    description="API for Spotify streaming history analysis",
    version="0.1.0",
)

# Configure CORS. Defaults to the same four origins as before; override with a
# comma-separated CORS_ORIGINS (Docker Compose sets this for the web container).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(mood.router)
app.include_router(discovery.router)
app.include_router(patterns.router)
app.include_router(milestones.router)
app.include_router(sessions.router)
app.include_router(reco.router)
app.include_router(sim.router)
app.include_router(compare.router)

@app.get("/")
async def root():
    return {
        "message": "Spotify Insights API",
        "version": "0.1.0",
        "status": "operational"
    }
