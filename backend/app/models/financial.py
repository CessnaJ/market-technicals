from sqlalchemy import Column, Integer, String, Date, Numeric, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class FinancialData(Base):
    """Financial data including PSR, PER, PBR, etc."""
    __tablename__ = "financial_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    period_type = Column(String(10), nullable=False)  # ANNUAL, QUARTER
    period_date = Column(Date, nullable=False)  # Settlement date

    # Financial statement data
    revenue = Column(Numeric(24, 0))  # Revenue (KRW)
    operating_income = Column(Numeric(24, 0))  # Operating income
    net_income = Column(Numeric(24, 0))  # Net income
    total_assets = Column(Numeric(24, 0))  # Total assets
    total_equity = Column(Numeric(24, 0))  # Total equity
    shares_outstanding = Column(BigInteger)  # Number of outstanding shares

    # Market data
    market_cap = Column(Numeric(24, 0))  # Market cap (KRW)

    # Financial ratios
    psr = Column(Numeric(10, 4))  # Price-to-Sales Ratio
    per = Column(Numeric(10, 4))  # Price-to-Earnings Ratio
    pbr = Column(Numeric(10, 4))  # Price-to-Book Ratio
    roe = Column(Numeric(10, 4))  # Return on Equity
    debt_ratio = Column(Numeric(10, 4))  # Debt Ratio

    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", backref="financial_data")

    def __repr__(self):
        return f"<FinancialData(ticker_id={self.stock_id}, period={self.period_date}, psr={self.psr})>"
