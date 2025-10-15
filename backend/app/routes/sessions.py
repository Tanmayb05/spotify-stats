from fastapi import APIRouter, Query
from typing import Optional
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/clusters")
async def get_session_clusters():
    """
    Get session cluster statistics and profiles
    """
    spotify_data.load_data()
    return spotify_data.get_session_clusters()


@router.get("/centroids")
async def get_session_centroids():
    """
    Get cluster centroids with feature values
    """
    spotify_data.load_data()
    return spotify_data.get_session_centroids()


@router.get("/assignments")
async def get_session_assignments(limit: int = Query(default=100, ge=1, le=500)):
    """
    Get recent sessions with their cluster assignments
    """
    spotify_data.load_data()
    return spotify_data.get_session_assignments(limit)
