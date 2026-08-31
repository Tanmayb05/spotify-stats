from fastapi import APIRouter, Query
from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("/list")
async def get_milestones_list(user_id: str | None = Query(None)):
    """
    Get all milestones - streaks, top days, firsts, and achievements
    """
    return supabase_data.get_milestones_list(user_id=user_id)


@router.get("/flashback")
async def get_flashback(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    user_id: str | None = Query(None),
):
    """
    Get detailed flashback for a specific date
    """
    return supabase_data.get_flashback(date, user_id=user_id)
