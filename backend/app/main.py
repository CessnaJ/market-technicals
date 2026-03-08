from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import redis_client
from app.services.preload_service import preload_service
from decimal import Decimal
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("🚀 기술적 분석 대시보드 API 시작 중...")
    await init_db()
    logger.info("🗄️ 데이터베이스 초기화 완료")
    resumed = await preload_service.resume_auto_sync_if_needed()
    if resumed:
        logger.info("🔄 중단된 universe preload 작업 자동 재개")
    yield
    # Shutdown
    logger.info("🛑 서버 종료 중...")
    await redis_client.disconnect()
    logger.info("🔌 Redis 연결 종료")


# Create FastAPI application
# Custom JSON encoder to handle Decimal properly
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Technical Analysis Dashboard for Korean Stock Market",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=JSONResponse,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "Technical Analysis Dashboard API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include API routers
from app.api.v1.router import router as api_v1_router
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
