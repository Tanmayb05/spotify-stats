from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io
import csv

from app.services.supabase_data_loader import supabase_data

router = APIRouter(prefix="/api", tags=["simulator"])


@router.get("/simulate/next")
async def simulate_next(
    n: int = Query(20, ge=1, le=50),
    seed: Optional[str] = Query(None, max_length=200),
    hour: Optional[int] = Query(None, ge=0, le=23),
    user_id: str | None = Query(None),
):
    """Simulate the next N plays as a most-probable walk over the artist Markov chain."""
    return supabase_data.get_simulation(seed=seed, n=n, hour=hour, user_id=user_id)


@router.get("/simulate/artists")
async def simulate_artists(user_id: str | None = Query(None)):
    """Artist names for the seed autocomplete (most-played first)."""
    return {"artists": supabase_data.get_sim_artists(user_id=user_id)}


@router.get("/export/simulation")
async def export_simulation(
    n: int = Query(50, ge=1, le=50),
    seed: Optional[str] = Query(None, max_length=200),
    hour: Optional[int] = Query(None, ge=0, le=23),
    user_id: str | None = Query(None),
):
    """Export a simulated sequence to CSV."""
    rows = supabase_data.get_simulation_csv_rows(seed=seed, n=n, hour=hour, user_id=user_id)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["step", "from_artist", "to_artist", "probability"],
    )
    writer.writeheader()
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=simulation.csv"},
    )
