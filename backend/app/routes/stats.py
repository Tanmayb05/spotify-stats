from fastapi import APIRouter, Query
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api", tags=["statistics"])


@router.get("/stats/overview")
async def get_overview():
    """Get overview statistics"""
    return spotify_data.get_overview_stats()


@router.get("/top/artists")
async def get_top_artists(limit: int = Query(10, ge=1, le=50)):
    """Get top artists by stream count"""
    return spotify_data.get_top_artists(limit=limit)


@router.get("/top/tracks")
async def get_top_tracks(limit: int = Query(10, ge=1, le=50)):
    """Get top tracks by stream count"""
    return spotify_data.get_top_tracks(limit=limit)


@router.get("/time/monthly")
async def get_monthly_data():
    """Get monthly streaming statistics"""
    return spotify_data.get_monthly_data()


@router.get("/platforms")
async def get_platform_stats():
    """Get platform usage statistics"""
    return spotify_data.get_platform_stats()
