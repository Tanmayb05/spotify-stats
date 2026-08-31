from fastapi import APIRouter, Query
from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api/patterns", tags=["listening_patterns"])


@router.get("/session-durations")
async def get_session_durations(user_id: str | None = Query(None)):
    """Get distribution of listening session durations"""
    return supabase_data.get_session_durations(user_id=user_id)


@router.get("/binge-sessions")
async def get_binge_sessions(
    limit: int = Query(20, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get top longest listening sessions (binge sessions)"""
    return supabase_data.get_binge_sessions(limit=limit, user_id=user_id)


@router.get("/session-statistics")
async def get_session_statistics(user_id: str | None = Query(None)):
    """Get aggregate session statistics"""
    return supabase_data.get_session_statistics(user_id=user_id)


@router.get("/weekend-weekday")
async def get_weekend_weekday(user_id: str | None = Query(None)):
    """Get weekend vs weekday listening comparison"""
    return supabase_data.get_weekend_weekday_comparison(user_id=user_id)


@router.get("/listening-streaks")
async def get_listening_streaks(
    limit: int = Query(10, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get consecutive day listening streaks"""
    return supabase_data.get_listening_streaks(limit=limit, user_id=user_id)


@router.get("/repeated-tracks")
async def get_repeated_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get most repeated tracks (tracks on repeat)"""
    return supabase_data.get_most_repeated_tracks(limit=limit, user_id=user_id)


@router.get("/monthly-diversity")
async def get_monthly_diversity(user_id: str | None = Query(None)):
    """Get artist diversity over time"""
    return supabase_data.get_monthly_diversity(user_id=user_id)


@router.get("/heatmap")
async def get_heatmap(user_id: str | None = Query(None)):
    """Get day-hour heatmap data"""
    return supabase_data.get_listening_heatmap(user_id=user_id)
