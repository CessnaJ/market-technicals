from sqlalchemy import Column, BigInteger, Integer, String, Date, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class IndicatorCache(Base):
    """Cache for calculated indicators to avoid recomputation"""
    __tablename__ = "indicator_cache"

    id = Column(BigInteger, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    indicator_name = Column(String(50), nullable=False)  # VPCI, WEINSTEIN_STAGE, etc.
    timeframe = Column(String(10), nullable=False)  # DAILY, WEEKLY
    parameters = Column(JSON, nullable=False, default={})
    date = Column(Date, nullable=False)
    value = Column(JSON, nullable=False)  # Calculated result (can have multiple values)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", backref="indicator_cache")

    def __repr__(self):
        return f"<IndicatorCache(ticker_id={self.stock_id}, indicator={self.indicator_name}, date={self.date})>"
