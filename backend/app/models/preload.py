from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class PricePreloadJob(Base):
    """Universe price preload queue/status table."""

    __tablename__ = "price_preload_jobs"

    id = Column(BigInteger, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    market = Column(String(20), index=True)
    target_days = Column(Integer, nullable=False, default=730)
    priority = Column(BigInteger, nullable=False, default=0, index=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    daily_records = Column(Integer, nullable=False, default=0)
    weekly_records = Column(Integer, nullable=False, default=0)
    last_synced_from = Column(Date)
    last_synced_to = Column(Date)
    last_run_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<PricePreloadJob(ticker={self.ticker}, status={self.status}, target_days={self.target_days})>"
