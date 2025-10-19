from fastapi import APIRouter, Query
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api/patterns", tags=["listening_patterns"])


@router.get("/session-durations")
async def get_session_durations():
    """Get distribution of listening session durations"""
    return spotify_data.get_session_durations()


@router.get("/binge-sessions")
async def get_binge_sessions(limit: int = Query(20, ge=1, le=50)):
    """Get top longest listening sessions (binge sessions)"""
    return spotify_data.get_binge_sessions(limit=limit)


@router.get("/session-statistics")
async def get_session_statistics():
    """Get aggregate session statistics"""
    return spotify_data.get_session_statistics()


@router.get("/weekend-weekday")
async def get_weekend_weekday():
    """Get weekend vs weekday listening comparison"""
    return spotify_data.get_weekend_weekday_comparison()


@router.get("/listening-streaks")
async def get_listening_streaks(limit: int = Query(10, ge=1, le=50)):
    """Get consecutive day listening streaks"""
    return spotify_data.get_listening_streaks(limit=limit)


@router.get("/repeated-tracks")
async def get_repeated_tracks(limit: int = Query(20, ge=1, le=50)):
    """Get most repeated tracks (tracks on repeat)"""
    return spotify_data.get_most_repeated_tracks(limit=limit)


@router.get("/monthly-diversity")
async def get_monthly_diversity():
    """Get artist diversity over time"""
    return spotify_data.get_monthly_diversity()


@router.get("/heatmap")
async def get_heatmap():
    """Get day-hour heatmap data"""
    return spotify_data.get_listening_heatmap()
