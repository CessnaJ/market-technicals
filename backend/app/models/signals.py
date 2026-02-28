from sqlalchemy import Column, BigInteger, Integer, String, Date, Numeric, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Signal(Base):
    """Trading signals log"""
    __tablename__ = "signals"

    id = Column(BigInteger, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False)  # WEINSTEIN_BREAKOUT, VPCI_DIVERGENCE, etc.
    signal_date = Column(Date, nullable=False)
    direction = Column(String(10), nullable=False)  # BULLISH, BEARISH, WARNING
    strength = Column(Numeric(5, 2))  # Confidence score 0-100
    is_false_signal = Column(Boolean)  # Post-verification result
    details = Column(JSON)  # Additional signal details
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", backref="signals")

    def __repr__(self):
        return f"<Signal(ticker_id={self.stock_id}, type={self.signal_type}, date={self.signal_date})>"
