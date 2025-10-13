from fastapi import APIRouter, Query
from typing import Optional
from app.services.data_loader import spotify_data

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/timeline")
async def get_discovery_timeline():
    """
    Get artist discovery timeline - when new artists were first discovered
    """
    spotify_data.load_data()
    return spotify_data.get_discovery_timeline()


@router.get("/loyalty")
async def get_artist_loyalty(limit: int = Query(default=20, ge=1, le=100)):
    """
    Get artist loyalty metrics - return probability and half-life
    """
    spotify_data.load_data()
    return spotify_data.get_artist_loyalty(limit)


@router.get("/obsessions")
async def get_artist_obsessions(limit: int = Query(default=15, ge=1, le=50)):
    """
    Get artist obsessions - periods where artist dominated listening
    """
    spotify_data.load_data()
    return spotify_data.get_artist_obsessions(limit)


@router.get("/reflect")
async def get_reflective_insights():
    """
    Get reflective insights about listening patterns
    """
    spotify_data.load_data()
    return spotify_data.get_reflective_insights()
