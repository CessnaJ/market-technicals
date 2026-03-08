from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class StockMaster(Base):
    """Search/source-of-truth universe for local stock metadata."""

    __tablename__ = "stock_master"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    standard_code = Column(String(20))
    name = Column(String(120), nullable=False, index=True)
    market = Column(String(20), index=True)
    sector_code = Column(String(10), index=True)
    sector_name = Column(String(120), index=True)
    industry_code = Column(String(10), index=True)
    industry_name = Column(String(120), index=True)
    market_cap = Column(BigInteger, default=0)
    listed_at = Column(Date)
    search_name = Column(String(160), nullable=False, index=True)
    search_initials = Column(String(160), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    themes = relationship("StockThemeMap", back_populates="stock", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StockMaster(ticker={self.ticker}, name={self.name})>"


class StockThemeMap(Base):
    """Theme mapping for related-stock discovery."""

    __tablename__ = "stock_theme_map"
    __table_args__ = (
        UniqueConstraint("stock_ticker", "theme_code", name="uq_stock_theme_map_stock_ticker_theme_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    stock_ticker = Column(String(20), ForeignKey("stock_master.ticker", ondelete="CASCADE"), nullable=False, index=True)
    theme_code = Column(String(10), nullable=False, index=True)
    theme_name = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    stock = relationship("StockMaster", back_populates="themes")

    def __repr__(self):
        return f"<StockThemeMap(stock_ticker={self.stock_ticker}, theme_code={self.theme_code})>"
