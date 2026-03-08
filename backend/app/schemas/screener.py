from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


ScreeningPreset = Literal["weinstein_stage2_start"]
ScreeningFilterName = Literal["vpci_positive", "rs_positive", "volume_confirmed", "not_extended"]
ScreeningRunStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]


class ScreeningScanRequest(BaseModel):
    preset: ScreeningPreset = "weinstein_stage2_start"
    benchmark_ticker: str = Field("069500", min_length=1, max_length=20)
    include_filters: list[ScreeningFilterName] = Field(default_factory=lambda: ["vpci_positive", "rs_positive"])
    stage_start_window_weeks: int = Field(8, ge=1, le=26)
    max_distance_to_30w_pct: float = Field(15.0, ge=1.0, le=50.0)
    volume_ratio_min: float = Field(1.5, ge=1.0, le=10.0)
    exclude_instruments: bool = True


class ScreeningFilterConfig(BaseModel):
    preset: ScreeningPreset
    benchmark_ticker: str
    include_filters: list[ScreeningFilterName]
    stage_start_window_weeks: int
    max_distance_to_30w_pct: float
    volume_ratio_min: float
    exclude_instruments: bool


class ScreeningSummaryItem(BaseModel):
    name: str
    count: int


class ScreeningSummary(BaseModel):
    sector_counts: list[ScreeningSummaryItem] = Field(default_factory=list)
    industry_counts: list[ScreeningSummaryItem] = Field(default_factory=list)
    score_buckets: list[ScreeningSummaryItem] = Field(default_factory=list)
    excluded_instruments: int = 0
    insufficient_data: int = 0
    filtered_out: int = 0
    total_evaluated: int = 0


class ScreeningRunStatusResponse(BaseModel):
    scan_id: int
    preset: ScreeningPreset
    request_hash: str
    status: ScreeningRunStatus
    benchmark_ticker: str
    filters: ScreeningFilterConfig
    total_candidates: int
    processed_candidates: int
    matched_count: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary: ScreeningSummary = Field(default_factory=ScreeningSummary)
    error_message: Optional[str] = None
    is_cached: bool = False
    cached_from_scan_id: Optional[int] = None


class ScreeningScanCreateResponse(ScreeningRunStatusResponse):
    started: bool
    already_running: bool = False
    message: str


class ScreeningResultRow(BaseModel):
    ticker: str
    name: str
    score: float
    rank: int
    sector: Optional[str] = None
    industry: Optional[str] = None
    stage_label: str
    weeks_since_stage2_start: Optional[int] = None
    distance_to_30w_pct: Optional[float] = None
    ma30w_slope_pct: Optional[float] = None
    mansfield_rs: Optional[float] = None
    vpci_value: Optional[float] = None
    volume_ratio: Optional[float] = None
    matched_filters: list[str] = Field(default_factory=list)
    failed_filters: list[str] = Field(default_factory=list)
    notes: dict = Field(default_factory=dict)


class ScreeningResultsResponse(BaseModel):
    scan_id: int
    total_count: int
    limit: int
    offset: int
    results: list[ScreeningResultRow] = Field(default_factory=list)
