from fastapi import APIRouter

from app.services.supabase_data_loader import supabase_data

# Phase 13 cull: only /users survives -- the web UserSwitcher needs it. The
# leaderboard / overlap / similarity-matrix / top-artists endpoints and the
# Comparison page were removed. The loader methods they called
# (get_leaderboard, get_overlap, get_similarity_matrix, get_top_artists_multi)
# remain in supabase_data_loader.py; Phase 14's loader collapse removes them.
router = APIRouter(prefix="/api/compare", tags=["comparison"])


@router.get("/users")
async def get_compare_users():
    """All users available in the multi-user switcher (primary user first)."""
    return supabase_data.list_users()
