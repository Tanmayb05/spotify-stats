from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.services.data_loader import spotify_data
import io
import csv

router = APIRouter(prefix="/api", tags=["statistics"])


@router.get("/stats/overview")
async def get_overview():
    """Get overview statistics"""
    return spotify_data.get_overview_stats()


@router.get("/top/artists")
async def get_top_artists(limit: int = Query(10, ge=1, le=50)):
    """Get top artists by stream count"""
    return spotify_data.get_top_artists(limit=limit)


@router.get("/top/tracks")
async def get_top_tracks(limit: int = Query(10, ge=1, le=50)):
    """Get top tracks by stream count"""
    return spotify_data.get_top_tracks(limit=limit)


@router.get("/time/monthly")
async def get_monthly_data():
    """Get monthly streaming statistics"""
    return spotify_data.get_monthly_data()


@router.get("/platforms")
async def get_platform_stats():
    """Get platform usage statistics"""
    return spotify_data.get_platform_stats()


@router.get("/stats/hourly")
async def get_hourly_stats():
    """Get hourly listening distribution (0-23)"""
    return spotify_data.get_hourly_distribution()


@router.get("/stats/daily")
async def get_daily_stats():
    """Get daily listening distribution (Mon-Sun)"""
    return spotify_data.get_daily_distribution()


@router.get("/stats/skip-behavior")
async def get_skip_behavior(limit: int = Query(20, ge=1, le=50)):
    """Get skip behavior analysis by artist"""
    return spotify_data.get_skip_behavior(limit=limit)


@router.get("/stats/yearly")
async def get_yearly_comparison():
    """Get year-over-year listening comparison"""
    return spotify_data.get_yearly_comparison()


# CSV Export Endpoints


@router.get("/export/top-artists")
async def export_top_artists(limit: int = Query(50, ge=1, le=100)):
    """Export top artists to CSV"""
    data = spotify_data.get_top_artists(limit=limit)

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
async def export_top_tracks(limit: int = Query(50, ge=1, le=100)):
    """Export top tracks to CSV"""
    data = spotify_data.get_top_tracks(limit=limit)

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
async def export_monthly_summary():
    """Export monthly summary to CSV"""
    data = spotify_data.get_monthly_data()

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
