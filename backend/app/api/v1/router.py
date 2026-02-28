from fastapi import APIRouter
from app.api.v1 import watchlist, fetch, chart, signals

router = APIRouter()

# Include sub-routers
router.include_router(watchlist.router)
router.include_router(fetch.router)
router.include_router(chart.router)
router.include_router(signals.router)

# Health check for v1 API
@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "v1"}
