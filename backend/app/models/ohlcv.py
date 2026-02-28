from sqlalchemy import Column, BigInteger, Integer, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class OHLCDaily(Base):
    """Daily OHLCV data"""
    __tablename__ = "ohlcv_daily"

    id = Column(BigInteger, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Numeric(18, 2), nullable=False)
    high = Column(Numeric(18, 2), nullable=False)
    low = Column(Numeric(18, 2), nullable=False)
    close = Column(Numeric(18, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    adj_close = Column(Numeric(18, 2))  # Adjusted close price
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", backref="daily_ohlcv")

    def __repr__(self):
        return f"<OHLCDaily(ticker_id={self.stock_id}, date={self.date}, close={self.close})>"


class OHLCWeekly(Base):
    """Weekly OHLCV data (calculated from daily)"""
    __tablename__ = "ohlcv_weekly"

    id = Column(BigInteger, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)  # Monday of the week
    open = Column(Numeric(18, 2), nullable=False)
    high = Column(Numeric(18, 2), nullable=False)
    low = Column(Numeric(18, 2), nullable=False)
    close = Column(Numeric(18, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", backref="weekly_ohlcv")

    def __repr__(self):
        return f"<OHLCWeekly(ticker_id={self.stock_id}, week_start={self.week_start}, close={self.close})>"
