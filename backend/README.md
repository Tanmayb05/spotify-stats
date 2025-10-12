# Spotify Stats API Backend

FastAPI backend for Spotify streaming history analysis.

## Setup

### Prerequisites
- Python 3.8 or higher

### Installation

**Note:** The backend uses the virtual environment from the root directory (`.venv`), not a local `venv`.

1. Activate the root virtual environment:
```bash
# From project root
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install backend dependencies:
```bash
cd backend
pip install -r requirements.txt
```

## Running the Server

### Development Mode
```bash
# From project root with .venv activated
cd backend
uvicorn app.main:app --reload --port 3011
```

The API will be available at:
- API: http://localhost:3011
- Interactive docs: http://localhost:3011/docs
- Alternative docs: http://localhost:3011/redoc

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 3011
```

## API Endpoints

### Health Check
- **GET** `/health` - Check API health status

### Future Endpoints (to be implemented)
- Phase 1: Overview stats, top artists/tracks, platform data
- Phase 2: Mood analysis endpoints
- Phase 3: Discovery and loyalty endpoints
- Phase 4: Milestones endpoints
- Phase 5: Session clustering endpoints
- Phase 6: ML recommendations endpoints
- Phase 7: Predictive simulation endpoints

## Development

### Project Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app initialization
│   └── routes/           # API route modules
│       ├── __init__.py
│       └── health.py     # Health check endpoint
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Adding New Endpoints
1. Create a new router file in `app/routes/`
2. Define your endpoints using FastAPI decorators
3. Include the router in `app/main.py`

Example:
```python
# app/routes/stats.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/stats", tags=["statistics"])

@router.get("/overview")
async def get_overview():
    return {"stats": "overview data"}
```

```python
# app/main.py
from app.routes import stats
app.include_router(stats.router)
```
