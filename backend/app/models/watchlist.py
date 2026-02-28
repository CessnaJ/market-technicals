from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Watchlist(Base):
    """Watchlist for tracking stocks of interest"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(100))
    memo = Column(Text)
    priority = Column(Integer, default=0)  # For sorting
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Watchlist(ticker={self.ticker}, name={self.name})>"
