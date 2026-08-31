from fastapi import APIRouter, Query
from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/clusters")
async def get_session_clusters(user_id: str | None = Query(None)):
    """
    Get session cluster statistics and profiles
    """
    return supabase_data.get_session_clusters(user_id=user_id)


@router.get("/centroids")
async def get_session_centroids(user_id: str | None = Query(None)):
    """
    Get cluster centroids with feature values
    """
    return supabase_data.get_session_centroids(user_id=user_id)


@router.get("/assignments")
async def get_session_assignments(
    limit: int = Query(default=100, ge=1, le=500),
    user_id: str | None = Query(None),
):
    """
    Get recent sessions with their cluster assignments
    """
    return supabase_data.get_session_assignments(limit, user_id=user_id)
