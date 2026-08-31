from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.services.supabase_data_loader import supabase_data
import io
import csv

router = APIRouter(prefix="/api", tags=["statistics"])


@router.get("/stats/overview")
async def get_overview(user_id: str | None = Query(None)):
    """Get overview statistics"""
    return supabase_data.get_overview_stats(user_id=user_id)


@router.get("/top/artists")
async def get_top_artists(
    limit: int = Query(10, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get top artists by stream count"""
    return supabase_data.get_top_artists(limit=limit, user_id=user_id)


@router.get("/top/tracks")
async def get_top_tracks(
    limit: int = Query(10, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get top tracks by stream count"""
    return supabase_data.get_top_tracks(limit=limit, user_id=user_id)


@router.get("/time/monthly")
async def get_monthly_data(user_id: str | None = Query(None)):
    """Get monthly streaming statistics"""
    return supabase_data.get_monthly_data(user_id=user_id)


@router.get("/platforms")
async def get_platform_stats(user_id: str | None = Query(None)):
    """Get platform usage statistics"""
    return supabase_data.get_platform_stats(user_id=user_id)


@router.get("/stats/hourly")
async def get_hourly_stats(user_id: str | None = Query(None)):
    """Get hourly listening distribution (0-23)"""
    return supabase_data.get_hourly_distribution(user_id=user_id)


@router.get("/stats/daily")
async def get_daily_stats(user_id: str | None = Query(None)):
    """Get daily listening distribution (Mon-Sun)"""
    return supabase_data.get_daily_distribution(user_id=user_id)


@router.get("/stats/skip-behavior")
async def get_skip_behavior(
    limit: int = Query(20, ge=1, le=50),
    user_id: str | None = Query(None),
):
    """Get skip behavior analysis by artist"""
    return supabase_data.get_skip_behavior(limit=limit, user_id=user_id)


@router.get("/stats/yearly")
async def get_yearly_comparison(user_id: str | None = Query(None)):
    """Get year-over-year listening comparison"""
    return supabase_data.get_yearly_comparison(user_id=user_id)


# CSV Export Endpoints


@router.get("/export/top-artists")
async def export_top_artists(
    limit: int = Query(50, ge=1, le=100),
    user_id: str | None = Query(None),
):
    """Export top artists to CSV"""
    data = supabase_data.get_top_artists(limit=limit, user_id=user_id)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['artist', 'streams'])
    writer.writeheader()
    writer.writerows(data)

    # Return as downloadable file
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=top_50_artists.csv"}
    )


@router.get("/export/top-tracks")
async def export_top_tracks(
    limit: int = Query(50, ge=1, le=100),
    user_id: str | None = Query(None),
):
    """Export top tracks to CSV"""
    data = supabase_data.get_top_tracks(limit=limit, user_id=user_id)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['track', 'artist', 'streams'])
    writer.writeheader()
    writer.writerows(data)

    # Return as downloadable file
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=top_50_tracks.csv"}
    )


@router.get("/export/monthly-summary")
async def export_monthly_summary(user_id: str | None = Query(None)):
    """Export monthly summary to CSV"""
    data = supabase_data.get_monthly_data(user_id=user_id)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['month', 'streams', 'hours'])
    writer.writeheader()
    writer.writerows(data)

    # Return as downloadable file
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=monthly_summary.csv"}
    )
