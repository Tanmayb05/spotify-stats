from fastapi import APIRouter, Query
from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/timeline")
async def get_discovery_timeline(user_id: str | None = Query(None)):
    """
    Get artist discovery timeline - when new artists were first discovered
    """
    return supabase_data.get_discovery_timeline(user_id=user_id)


@router.get("/loyalty")
async def get_artist_loyalty(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str | None = Query(None),
):
    """
    Get artist loyalty metrics - return probability and half-life
    """
    return supabase_data.get_artist_loyalty(limit, user_id=user_id)


@router.get("/obsessions")
async def get_artist_obsessions(
    limit: int = Query(default=15, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """
    Get artist obsessions - periods where artist dominated listening
    """
    return supabase_data.get_artist_obsessions(limit, user_id=user_id)


@router.get("/reflect")
async def get_reflective_insights(user_id: str | None = Query(None)):
    """
    Get reflective insights about listening patterns
    """
    return supabase_data.get_reflective_insights(user_id=user_id)
