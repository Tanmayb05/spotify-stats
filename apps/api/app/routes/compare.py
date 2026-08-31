from fastapi import APIRouter, Query, HTTPException
from typing import List

from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api/compare", tags=["comparison"])


def _parse_users(users: str, *, min_n: int = 2, max_n: int = 6) -> List[str]:
    """Split a comma-separated user_id list and validate against known users."""
    ids = [u.strip() for u in users.split(",") if u.strip()]
    if not (min_n <= len(ids) <= max_n):
        raise HTTPException(
            status_code=400,
            detail=f"Provide between {min_n} and {max_n} comma-separated user ids",
        )
    known = {u["user_id"] for u in supabase_data.list_users()}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown user id(s): {unknown}")
    return ids


@router.get("/users")
async def get_compare_users():
    """All users available for comparison (primary user first)."""
    return supabase_data.list_users()


@router.get("/leaderboard")
async def get_leaderboard():
    """Per-user listening totals: streams, hours, artists, skip rate, date range."""
    return supabase_data.get_leaderboard()


@router.get("/overlap")
async def get_overlap(
    users: str = Query(..., description="2-6 comma-separated user ids"),
    top_n: int = Query(25, ge=1, le=100),
):
    """Shared-artist overlap and Jaccard similarity between the given users."""
    ids = _parse_users(users)
    return supabase_data.get_overlap(ids, top_n=top_n)


@router.get("/similarity-matrix")
async def get_similarity_matrix():
    """N x N pairwise artist-Jaccard % across all users (diagonal null)."""
    return supabase_data.get_similarity_matrix()


@router.get("/top-artists")
async def get_top_artists_multi(
    users: str = Query(..., description="1-6 comma-separated user ids"),
    limit: int = Query(10, ge=1, le=50),
):
    """Each selected user's top `limit` artists, keyed by display name."""
    ids = _parse_users(users, min_n=1)
    return supabase_data.get_top_artists_multi(ids, limit=limit)
