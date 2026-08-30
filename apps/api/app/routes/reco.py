from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io
import csv

from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api", tags=["recommendations"])

_MOOD_RE = "^(happy|energetic|chill)$"


@router.get("/reco")
async def get_reco(
    top_k: int = Query(20, ge=1, le=100),
    target_mood: Optional[str] = Query(None, regex=_MOOD_RE),
):
    """Content-based track recommendations with 'why this' feature attribution."""
    return spotify_data.get_recommendations(top_k=top_k, target_mood=target_mood)


@router.get("/export/recommendations")
async def export_recommendations(
    top_k: int = Query(50, ge=1, le=200),
    target_mood: Optional[str] = Query(None, regex=_MOOD_RE),
):
    """Export recommendations to CSV."""
    rows = spotify_data.get_recommendations_csv_rows(top_k=top_k, target_mood=target_mood)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["track", "artist", "album", "score", "play_count", "why"],
    )
    writer.writeheader()
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=recommendations.csv"},
    )
