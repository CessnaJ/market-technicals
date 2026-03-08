from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ScreeningRun(Base):
    """Universe screening run metadata and summary."""

    __tablename__ = "screening_runs"

    id = Column(BigInteger, primary_key=True, index=True)
    preset = Column(String(50), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    benchmark_ticker = Column(String(20), nullable=False)
    filters_json = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    total_candidates = Column(Integer, nullable=False, default=0)
    processed_candidates = Column(Integer, nullable=False, default=0)
    matched_count = Column(Integer, nullable=False, default=0)
    summary_json = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    results = relationship("ScreeningResult", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ScreeningRun(id={self.id}, preset={self.preset}, status={self.status})>"


class ScreeningResult(Base):
    """Stored ranked screener results for a completed run."""

    __tablename__ = "screening_results"
    __table_args__ = (
        UniqueConstraint("run_id", "ticker", name="uq_screening_results_run_id_ticker"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(BigInteger, ForeignKey("screening_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False, index=True)
    sector = Column(String(120))
    industry = Column(String(120))
    stage_label = Column(String(50), nullable=False)
    weeks_since_stage2_start = Column(Integer)
    distance_to_30w_pct = Column(Float)
    ma30w_slope_pct = Column(Float)
    mansfield_rs = Column(Float)
    vpci_value = Column(Float)
    volume_ratio = Column(Float)
    matched_filters_json = Column(JSON, nullable=False, default=list)
    failed_filters_json = Column(JSON, nullable=False, default=list)
    notes_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("ScreeningRun", back_populates="results")

    def __repr__(self):
        return f"<ScreeningResult(run_id={self.run_id}, ticker={self.ticker}, score={self.score})>"
