from fastapi import APIRouter, Query
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api/mood", tags=["mood"])


@router.get("/summary")
async def get_mood_summary(window: str = Query("30d", regex="^(7d|30d|90d|all)$")):
    """
    Get mood summary for a time window

    Args:
        window: Time window (7d, 30d, 90d, or all)

    Returns:
        Average valence, energy, and danceability for the period
    """
    # Parse window
    if window == "all":
        window_days = 36500  # ~100 years
    else:
        window_days = int(window.rstrip('d'))

    return spotify_data.get_mood_summary(window_days=window_days)


@router.get("/contexts")
async def get_mood_contexts():
    """
    Get mood comparisons across different contexts

    Returns:
        Mood metrics for weekday vs weekend and by platform
    """
    return spotify_data.get_mood_contexts()


@router.get("/monthly")
async def get_mood_monthly():
    """
    Get monthly mood trends over time

    Returns:
        List of monthly average mood metrics
    """
    return spotify_data.get_mood_monthly()
