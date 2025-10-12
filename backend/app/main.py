from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, stats

# Create FastAPI app
app = FastAPI(
    title="Spotify Stats API",
    description="API for Spotify streaming history analysis",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3010",  # Frontend dev server
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",  # Alternative dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(stats.router)

@app.get("/")
async def root():
    return {
        "message": "Spotify Stats API",
        "version": "0.1.0",
        "status": "operational"
    }
