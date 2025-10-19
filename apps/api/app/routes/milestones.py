from fastapi import APIRouter, Query
from typing import Optional
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("/list")
async def get_milestones_list():
    """
    Get all milestones - streaks, top days, firsts, and achievements
    """
    spotify_data.load_data()
    return spotify_data.get_milestones_list()


@router.get("/flashback")
async def get_flashback(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Get detailed flashback for a specific date
    """
    spotify_data.load_data()
    return spotify_data.get_flashback(date)
