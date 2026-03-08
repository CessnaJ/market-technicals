from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import re
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.database import async_session_maker, engine
from app.indicators.custom.vpci import VPCI
from app.indicators.custom.weinstein import WeinsteinAnalysis
from app.models import OHLCDaily, OHLCWeekly, ScreeningResult, ScreeningRun, Stock, StockMaster
from app.schemas import (
    ScreeningFilterConfig,
    ScreeningResultsResponse,
    ScreeningResultRow,
    ScreeningRunStatusResponse,
    ScreeningScanCreateResponse,
    ScreeningScanRequest,
    ScreeningSummary,
    ScreeningSummaryItem,
)

logger = logging.getLogger(__name__)

SCREENING_CACHE_MINUTES = 15
SCREENING_CHUNK_SIZE = 150
SCREENING_LOCK_KEY_1 = 16180
SCREENING_LOCK_KEY_2 = 33988
WEEKLY_LOOKBACK_WEEKS = 130
DAILY_LOOKBACK_DAYS = 140

ETF_NAME_PATTERNS = (
    "KODEX",
    "TIGER",
    "KBSTAR",
    "KINDEX",
    "KOSEF",
    "ARIRANG",
    "HANARO",
    "ACE",
    "SOL",
    "PLUS",
    "RISE",
    "TIMEFOLIO",
    "TREX",
    "SMART",
    "FOCUS",
    "TRUSTON",
    "마이티",
)

PREFERRED_SUFFIX_PATTERN = re.compile(r"(우|우B|우C|1우|2우|3우|우선주)$")


@dataclass
class CandidateEvaluation:
    outcome: str
    result: Optional[dict] = None


class ScreenerService:
    def __init__(self):
        self._background_task: asyncio.Task | None = None
        self._background_lock = asyncio.Lock()
        self._lock_connection: AsyncConnection | None = None
        self.weinstein = WeinsteinAnalysis()
        self.vpci = VPCI()

    def is_running(self) -> bool:
        return self._background_task is not None and not self._background_task.done()

    async def _acquire_runner_lock(self) -> bool:
        if self._lock_connection is not None:
            return True

        connection = await engine.connect()
        try:
            acquired = await connection.scalar(
                text("select pg_try_advisory_lock(:key1, :key2)"),
                {"key1": SCREENING_LOCK_KEY_1, "key2": SCREENING_LOCK_KEY_2},
            )
            if acquired:
                self._lock_connection = connection
                return True
        except Exception:
            await connection.close()
            raise

        await connection.close()
        return False

    async def _release_runner_lock(self):
        if self._lock_connection is None:
            return

        try:
            await self._lock_connection.scalar(
                text("select pg_advisory_unlock(:key1, :key2)"),
                {"key1": SCREENING_LOCK_KEY_1, "key2": SCREENING_LOCK_KEY_2},
            )
        finally:
            await self._lock_connection.close()
            self._lock_connection = None

    async def is_global_runner_active(self, db: AsyncSession) -> bool:
        active = await db.scalar(
            text(
                """
                select exists (
                    select 1
                    from pg_locks
                    where locktype = 'advisory'
                      and classid = :key1
                      and objid = :key2
                      and granted = true
                )
                """
            ),
            {"key1": SCREENING_LOCK_KEY_1, "key2": SCREENING_LOCK_KEY_2},
        )
        return bool(active)

    def _normalize_filter_names(self, include_filters: Iterable[str]) -> list[str]:
        ordered: list[str] = []
        for item in include_filters:
            value = (item or "").strip()
            if value and value not in ordered:
                ordered.append(value)
        return sorted(ordered)

    def normalize_scan_request(self, payload: ScreeningScanRequest) -> ScreeningFilterConfig:
        return ScreeningFilterConfig(
            preset=payload.preset,
            benchmark_ticker=payload.benchmark_ticker.strip().upper(),
            include_filters=self._normalize_filter_names(payload.include_filters),
            stage_start_window_weeks=payload.stage_start_window_weeks,
            max_distance_to_30w_pct=float(payload.max_distance_to_30w_pct),
            volume_ratio_min=float(payload.volume_ratio_min),
            exclude_instruments=payload.exclude_instruments,
        )

    def build_request_hash(self, config: ScreeningFilterConfig) -> str:
        serialized = json.dumps(config.model_dump(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _summary_from_json(self, raw_summary: dict | None) -> ScreeningSummary:
        payload = raw_summary or {}
        return ScreeningSummary(
            sector_counts=[ScreeningSummaryItem(**item) for item in payload.get("sector_counts", [])],
            industry_counts=[ScreeningSummaryItem(**item) for item in payload.get("industry_counts", [])],
            score_buckets=[ScreeningSummaryItem(**item) for item in payload.get("score_buckets", [])],
            excluded_instruments=int(payload.get("excluded_instruments", 0)),
            insufficient_data=int(payload.get("insufficient_data", 0)),
            filtered_out=int(payload.get("filtered_out", 0)),
            total_evaluated=int(payload.get("total_evaluated", 0)),
        )

    def _run_to_response(
        self,
        run: ScreeningRun,
        *,
        is_cached: bool = False,
        cached_from_scan_id: int | None = None,
    ) -> ScreeningRunStatusResponse:
        filters = ScreeningFilterConfig(**(run.filters_json or {}))
        return ScreeningRunStatusResponse(
            scan_id=run.id,
            preset=run.preset,
            request_hash=run.request_hash,
            status=run.status,
            benchmark_ticker=run.benchmark_ticker,
            filters=filters,
            total_candidates=run.total_candidates or 0,
            processed_candidates=run.processed_candidates or 0,
            matched_count=run.matched_count or 0,
            started_at=run.started_at,
            finished_at=run.finished_at,
            summary=self._summary_from_json(run.summary_json),
            error_message=run.error_message,
            is_cached=is_cached,
            cached_from_scan_id=cached_from_scan_id,
        )

    async def recover_interrupted_runs(self, db: AsyncSession) -> int:
        if await self.is_global_runner_active(db):
            return 0

        result = await db.execute(
            update(ScreeningRun)
            .where(ScreeningRun.status == "RUNNING")
            .values(
                status="FAILED",
                finished_at=datetime.now(),
                error_message="Recovered from interrupted screener background task",
            )
        )
        await db.commit()
        recovered = result.rowcount or 0
        if recovered > 0:
            logger.warning("SCREENER_RECOVER_INTERRUPTED recovered=%s", recovered)
        return recovered

    async def create_scan(self, payload: ScreeningScanRequest) -> ScreeningScanCreateResponse:
        config = self.normalize_scan_request(payload)
        request_hash = self.build_request_hash(config)

        async with self._background_lock:
            async with async_session_maker() as db:
                await self.recover_interrupted_runs(db)

                cached_cutoff = datetime.now() - timedelta(minutes=SCREENING_CACHE_MINUTES)
                cached_run = await db.scalar(
                    select(ScreeningRun)
                    .where(
                        ScreeningRun.request_hash == request_hash,
                        ScreeningRun.status == "COMPLETED",
                        ScreeningRun.finished_at.is_not(None),
                        ScreeningRun.finished_at >= cached_cutoff,
                    )
                    .order_by(ScreeningRun.finished_at.desc())
                    .limit(1)
                )
                if cached_run is not None:
                    base = self._run_to_response(
                        cached_run,
                        is_cached=True,
                        cached_from_scan_id=cached_run.id,
                    )
                    return ScreeningScanCreateResponse(
                        **base.model_dump(),
                        started=False,
                        already_running=False,
                        message="Recent cached screener result reused",
                    )

                running_same = await db.scalar(
                    select(ScreeningRun)
                    .where(
                        ScreeningRun.request_hash == request_hash,
                        ScreeningRun.status.in_(["PENDING", "RUNNING"]),
                    )
                    .order_by(ScreeningRun.created_at.desc())
                    .limit(1)
                )
                if running_same is not None:
                    base = self._run_to_response(running_same)
                    return ScreeningScanCreateResponse(
                        **base.model_dump(),
                        started=False,
                        already_running=True,
                        message="Same screener request is already running",
                    )

                if await self.is_global_runner_active(db):
                    active_run = await db.scalar(
                        select(ScreeningRun)
                        .where(ScreeningRun.status.in_(["PENDING", "RUNNING"]))
                        .order_by(ScreeningRun.created_at.desc())
                        .limit(1)
                    )
                    if active_run is not None:
                        base = self._run_to_response(active_run)
                        return ScreeningScanCreateResponse(
                            **base.model_dump(),
                            started=False,
                            already_running=True,
                            message="Another screener run is already active",
                        )

                total_candidates = int(await db.scalar(select(func.count(StockMaster.id))) or 0)
                run = ScreeningRun(
                    preset=config.preset,
                    request_hash=request_hash,
                    status="PENDING",
                    benchmark_ticker=config.benchmark_ticker,
                    filters_json=config.model_dump(),
                    total_candidates=total_candidates,
                    processed_candidates=0,
                    matched_count=0,
                    summary_json=ScreeningSummary().model_dump(),
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)

            self._background_task = asyncio.create_task(self._run_scan_background(run.id))

        base = self._run_to_response(run)
        return ScreeningScanCreateResponse(
            **base.model_dump(),
            started=True,
            already_running=False,
            message="Screener run started",
        )

    async def get_scan(self, db: AsyncSession, scan_id: int) -> ScreeningRunStatusResponse | None:
        await self.recover_interrupted_runs(db)
        run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == scan_id))
        if run is None:
            return None
        return self._run_to_response(run)

    async def get_latest_scan(
        self,
        db: AsyncSession,
        *,
        preset: str,
        benchmark_ticker: str,
        filters_hash: str,
    ) -> ScreeningRunStatusResponse | None:
        await self.recover_interrupted_runs(db)
        run = await db.scalar(
            select(ScreeningRun)
            .where(
                ScreeningRun.preset == preset,
                ScreeningRun.benchmark_ticker == benchmark_ticker.upper(),
                ScreeningRun.request_hash == filters_hash,
            )
            .order_by(ScreeningRun.created_at.desc())
            .limit(1)
        )
        if run is None:
            return None
        return self._run_to_response(run)

    async def get_results(
        self,
        db: AsyncSession,
        *,
        scan_id: int,
        limit: int,
        offset: int,
    ) -> ScreeningResultsResponse:
        total_count = int(
            await db.scalar(select(func.count(ScreeningResult.id)).where(ScreeningResult.run_id == scan_id)) or 0
        )
        rows = (
            await db.execute(
                select(ScreeningResult)
                .where(ScreeningResult.run_id == scan_id)
                .order_by(ScreeningResult.rank.asc(), ScreeningResult.ticker.asc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return ScreeningResultsResponse(
            scan_id=scan_id,
            total_count=total_count,
            limit=limit,
            offset=offset,
            results=[
                ScreeningResultRow(
                    ticker=row.ticker,
                    name=row.name,
                    score=float(row.score),
                    rank=row.rank,
                    sector=row.sector,
                    industry=row.industry,
                    stage_label=row.stage_label,
                    weeks_since_stage2_start=row.weeks_since_stage2_start,
                    distance_to_30w_pct=row.distance_to_30w_pct,
                    ma30w_slope_pct=row.ma30w_slope_pct,
                    mansfield_rs=row.mansfield_rs,
                    vpci_value=row.vpci_value,
                    volume_ratio=row.volume_ratio,
                    matched_filters=list(row.matched_filters_json or []),
                    failed_filters=list(row.failed_filters_json or []),
                    notes=dict(row.notes_json or {}),
                )
                for row in rows
            ],
        )

    async def _run_scan_background(self, run_id: int):
        acquired = False
        try:
            acquired = await self._acquire_runner_lock()
            if not acquired:
                async with async_session_maker() as db:
                    run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
                    if run is not None:
                        run.status = "FAILED"
                        run.finished_at = datetime.now()
                        run.error_message = "Another screener runner is already active"
                        await db.commit()
                return

            async with async_session_maker() as db:
                run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
                if run is None:
                    return
                run.status = "RUNNING"
                run.started_at = datetime.now()
                run.error_message = None
                await db.commit()

            await self._execute_scan(run_id)
        except Exception as exc:
            logger.exception("❌ Screener background run failed: %s", exc)
            async with async_session_maker() as db:
                run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
                if run is not None:
                    run.status = "FAILED"
                    run.finished_at = datetime.now()
                    run.error_message = str(exc)[:500]
                    await db.commit()
        finally:
            self._background_task = None
            if acquired:
                await self._release_runner_lock()

    async def _execute_scan(self, run_id: int):
        async with async_session_maker() as db:
            run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
            if run is None:
                return
            config = ScreeningFilterConfig(**(run.filters_json or {}))

        benchmark_by_date = await self._load_benchmark_series(config.benchmark_ticker)
        all_matches: list[dict] = []
        summary_counter = {
            "excluded_instruments": 0,
            "insufficient_data": 0,
            "filtered_out": 0,
            "total_evaluated": 0,
        }

        offset = 0
        while True:
            async with async_session_maker() as db:
                masters = (
                    await db.execute(
                        select(StockMaster)
                        .order_by(StockMaster.market_cap.desc(), StockMaster.ticker.asc())
                        .limit(SCREENING_CHUNK_SIZE)
                        .offset(offset)
                    )
                ).scalars().all()

                if not masters:
                    break

                chunk_matches, chunk_summary = await self._process_chunk(
                    db,
                    masters=masters,
                    config=config,
                    benchmark_by_date=benchmark_by_date,
                )
                all_matches.extend(chunk_matches)
                for key, value in chunk_summary.items():
                    summary_counter[key] += value

                run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
                if run is not None:
                    run.processed_candidates = summary_counter["total_evaluated"]
                    run.matched_count = len(all_matches)
                    run.summary_json = self._build_summary_payload(all_matches, summary_counter)
                    await db.commit()

            offset += SCREENING_CHUNK_SIZE

        ranked_results = self._rank_results(all_matches)
        summary_payload = self._build_summary_payload(ranked_results, summary_counter)

        async with async_session_maker() as db:
            await db.execute(delete(ScreeningResult).where(ScreeningResult.run_id == run_id))
            db.add_all(
                [
                    ScreeningResult(
                        run_id=run_id,
                        ticker=item["ticker"],
                        name=item["name"],
                        score=item["score"],
                        rank=item["rank"],
                        sector=item["sector"],
                        industry=item["industry"],
                        stage_label=item["stage_label"],
                        weeks_since_stage2_start=item["weeks_since_stage2_start"],
                        distance_to_30w_pct=item["distance_to_30w_pct"],
                        ma30w_slope_pct=item["ma30w_slope_pct"],
                        mansfield_rs=item["mansfield_rs"],
                        vpci_value=item["vpci_value"],
                        volume_ratio=item["volume_ratio"],
                        matched_filters_json=item["matched_filters"],
                        failed_filters_json=item["failed_filters"],
                        notes_json=item["notes"],
                    )
                    for item in ranked_results
                ]
            )

            run = await db.scalar(select(ScreeningRun).where(ScreeningRun.id == run_id))
            if run is not None:
                run.status = "COMPLETED"
                run.finished_at = datetime.now()
                run.processed_candidates = summary_counter["total_evaluated"]
                run.matched_count = len(ranked_results)
                run.summary_json = summary_payload
            await db.commit()

        logger.info(
            "SCREENER_RUN_COMPLETED run_id=%s matched=%s evaluated=%s filtered_out=%s insufficient=%s excluded=%s",
            run_id,
            len(ranked_results),
            summary_counter["total_evaluated"],
            summary_counter["filtered_out"],
            summary_counter["insufficient_data"],
            summary_counter["excluded_instruments"],
        )

    async def _load_benchmark_series(self, benchmark_ticker: str) -> pd.DataFrame:
        async with async_session_maker() as db:
            benchmark_stock = await db.scalar(select(Stock).where(Stock.ticker == benchmark_ticker))
            if benchmark_stock is None:
                return pd.DataFrame()

            cutoff = datetime.now().date() - timedelta(days=WEEKLY_LOOKBACK_WEEKS * 7 + 90)
            weekly_rows = (
                await db.execute(
                    select(OHLCWeekly)
                    .where(
                        OHLCWeekly.stock_id == benchmark_stock.id,
                        OHLCWeekly.week_start >= cutoff,
                    )
                    .order_by(OHLCWeekly.week_start.asc())
                )
            ).scalars().all()
        return self._weekly_rows_to_dataframe(weekly_rows)

    async def _process_chunk(
        self,
        db: AsyncSession,
        *,
        masters: list[StockMaster],
        config: ScreeningFilterConfig,
        benchmark_by_date: pd.DataFrame,
    ) -> tuple[list[dict], dict[str, int]]:
        summary_counter = {
            "excluded_instruments": 0,
            "insufficient_data": 0,
            "filtered_out": 0,
            "total_evaluated": 0,
        }

        candidate_masters: list[StockMaster] = []
        for master in masters:
            summary_counter["total_evaluated"] += 1
            if config.exclude_instruments and self.is_excluded_instrument(master.name):
                summary_counter["excluded_instruments"] += 1
                continue
            candidate_masters.append(master)

        if not candidate_masters:
            return [], summary_counter

        tickers = [master.ticker for master in candidate_masters]
        stock_rows = (
            await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))
        ).scalars().all()
        stock_by_ticker = {stock.ticker: stock for stock in stock_rows}

        stock_ids = [stock.id for stock in stock_rows]
        if not stock_ids:
            summary_counter["insufficient_data"] += len(candidate_masters)
            return [], summary_counter

        daily_cutoff = datetime.now().date() - timedelta(days=DAILY_LOOKBACK_DAYS)
        weekly_cutoff = datetime.now().date() - timedelta(days=WEEKLY_LOOKBACK_WEEKS * 7 + 90)

        daily_rows = (
            await db.execute(
                select(OHLCDaily)
                .where(
                    OHLCDaily.stock_id.in_(stock_ids),
                    OHLCDaily.date >= daily_cutoff,
                )
                .order_by(OHLCDaily.stock_id.asc(), OHLCDaily.date.asc())
            )
        ).scalars().all()
        weekly_rows = (
            await db.execute(
                select(OHLCWeekly)
                .where(
                    OHLCWeekly.stock_id.in_(stock_ids),
                    OHLCWeekly.week_start >= weekly_cutoff,
                )
                .order_by(OHLCWeekly.stock_id.asc(), OHLCWeekly.week_start.asc())
            )
        ).scalars().all()

        daily_by_stock_id: dict[int, list] = defaultdict(list)
        weekly_by_stock_id: dict[int, list] = defaultdict(list)
        for row in daily_rows:
            daily_by_stock_id[row.stock_id].append(row)
        for row in weekly_rows:
            weekly_by_stock_id[row.stock_id].append(row)

        matches: list[dict] = []
        for master in candidate_masters:
            stock = stock_by_ticker.get(master.ticker)
            if stock is None:
                summary_counter["insufficient_data"] += 1
                continue

            evaluation = self.evaluate_candidate(
                master=master,
                weekly_df=self._weekly_rows_to_dataframe(weekly_by_stock_id.get(stock.id, [])),
                daily_df=self._daily_rows_to_dataframe(daily_by_stock_id.get(stock.id, [])),
                benchmark_weekly_df=benchmark_by_date,
                config=config,
            )

            if evaluation.outcome == "matched" and evaluation.result is not None:
                matches.append(evaluation.result)
            elif evaluation.outcome == "insufficient_data":
                summary_counter["insufficient_data"] += 1
            else:
                summary_counter["filtered_out"] += 1

        return matches, summary_counter

    def evaluate_candidate(
        self,
        *,
        master: StockMaster,
        weekly_df: pd.DataFrame,
        daily_df: pd.DataFrame,
        benchmark_weekly_df: pd.DataFrame,
        config: ScreeningFilterConfig,
    ) -> CandidateEvaluation:
        if weekly_df.empty or len(weekly_df) < 40 or daily_df.empty or len(daily_df) < 25:
            return CandidateEvaluation(outcome="insufficient_data")

        analysis = self.weinstein.analyze(weekly_df)
        if not analysis:
            return CandidateEvaluation(outcome="insufficient_data")

        stage_series = analysis["stage"]
        ma_series = analysis["ma_30w"]
        slope_series = analysis["ma_slope"]
        slope_pct_series = analysis["ma_slope_pct"]
        distance_series = analysis["distance_to_ma"]

        current_stage = int(stage_series.iloc[-1]) if pd.notna(stage_series.iloc[-1]) else 0
        current_ma = ma_series.iloc[-1]
        current_slope = slope_series.iloc[-1]
        current_slope_pct = slope_pct_series.iloc[-1]
        current_distance = distance_series.iloc[-1]
        current_close = float(weekly_df["close"].iloc[-1])

        if (
            current_stage != 2
            or pd.isna(current_ma)
            or pd.isna(current_slope_pct)
            or current_close <= float(current_ma)
            or current_slope != "RISING"
            or float(current_slope_pct) <= 0
        ):
            return CandidateEvaluation(outcome="filtered_out")

        transition_index = self._find_recent_stage2_transition(stage_series)
        if transition_index is None:
            return CandidateEvaluation(outcome="filtered_out")

        weeks_since_stage2_start = len(stage_series) - 1 - transition_index
        if weeks_since_stage2_start > config.stage_start_window_weeks:
            return CandidateEvaluation(outcome="filtered_out")

        distance_to_30w_pct = float(current_distance) if pd.notna(current_distance) else None
        ma30w_slope_pct = float(current_slope_pct)
        volume_ratio = self._calculate_breakout_volume_ratio(weekly_df, transition_index)

        matched_filters = ["stage2_start"]
        failed_filters: list[str] = []

        core_score = self._calculate_core_score(
            weeks_since_stage2_start=weeks_since_stage2_start,
            stage_window_weeks=config.stage_start_window_weeks,
            ma30w_slope_pct=ma30w_slope_pct,
            distance_to_30w_pct=distance_to_30w_pct,
            max_distance_to_30w_pct=config.max_distance_to_30w_pct,
        )
        score = core_score

        vpci_value, vpci_passed = self._evaluate_vpci(daily_df)
        mansfield_rs, rs_passed = self._evaluate_relative_strength(weekly_df, benchmark_weekly_df)
        volume_passed = volume_ratio is not None and volume_ratio >= config.volume_ratio_min
        not_extended = (
            distance_to_30w_pct is not None
            and distance_to_30w_pct <= config.max_distance_to_30w_pct
        )

        module_results = {
            "vpci_positive": (vpci_passed, 15.0),
            "rs_positive": (rs_passed, 15.0),
            "volume_confirmed": (volume_passed, 10.0),
            "not_extended": (not_extended, 0.0),
        }

        for filter_name in config.include_filters:
            passed, _weight = module_results[filter_name]
            if passed:
                matched_filters.append(filter_name)
            else:
                failed_filters.append(filter_name)

        if failed_filters:
            return CandidateEvaluation(outcome="filtered_out")

        if vpci_passed:
            score += 15.0
            if "vpci_positive" not in matched_filters:
                matched_filters.append("vpci_positive")
        if rs_passed:
            score += 15.0
            if "rs_positive" not in matched_filters:
                matched_filters.append("rs_positive")
        if volume_passed:
            score += 10.0
            if "volume_confirmed" not in matched_filters:
                matched_filters.append("volume_confirmed")
        if not not_extended:
            score = max(0.0, score - 10.0)

        transition_date = weekly_df["date"].iloc[transition_index]
        result = {
            "ticker": master.ticker,
            "name": master.name,
            "score": round(score, 2),
            "rank": 0,
            "sector": master.sector_name or None,
            "industry": master.industry_name or None,
            "stage_label": str(analysis["stage_label"].iloc[-1]),
            "weeks_since_stage2_start": weeks_since_stage2_start,
            "distance_to_30w_pct": round(distance_to_30w_pct, 2) if distance_to_30w_pct is not None else None,
            "ma30w_slope_pct": round(ma30w_slope_pct, 2),
            "mansfield_rs": round(mansfield_rs, 2) if mansfield_rs is not None else None,
            "vpci_value": round(vpci_value, 4) if vpci_value is not None else None,
            "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            "matched_filters": sorted(set(matched_filters)),
            "failed_filters": [],
            "notes": {
                "transition_date": transition_date.isoformat() if hasattr(transition_date, "isoformat") else str(transition_date),
                "current_close": round(current_close, 2),
                "ma30w": round(float(current_ma), 2),
                "exclude_instruments": config.exclude_instruments,
            },
        }
        return CandidateEvaluation(outcome="matched", result=result)

    def _find_recent_stage2_transition(self, stage_series: pd.Series) -> int | None:
        last_transition_index = None
        for index in range(1, len(stage_series)):
            current_value = stage_series.iloc[index]
            previous_value = stage_series.iloc[index - 1]
            if pd.isna(current_value) or pd.isna(previous_value):
                continue
            if int(current_value) == 2 and int(previous_value) != 2:
                last_transition_index = index
        return last_transition_index

    def _calculate_breakout_volume_ratio(self, weekly_df: pd.DataFrame, transition_index: int) -> float | None:
        if transition_index < 10:
            return None
        breakout_volume = float(weekly_df["volume"].iloc[transition_index])
        prior_average = float(weekly_df["volume"].iloc[transition_index - 10:transition_index].mean())
        if prior_average <= 0:
            return None
        return breakout_volume / prior_average

    def _evaluate_vpci(self, daily_df: pd.DataFrame) -> tuple[float | None, bool]:
        result = self.vpci.calculate(daily_df)
        vpci_series = result.get("vpci")
        if vpci_series is None or len(vpci_series) < 5:
            return None, False

        latest = vpci_series.iloc[-1]
        trailing = vpci_series.iloc[-5]
        if pd.isna(latest) or pd.isna(trailing):
            return None, False
        latest_value = float(latest)
        trend_delta = float(latest - trailing)
        return latest_value, latest_value > 0 and trend_delta >= 0

    def _evaluate_relative_strength(
        self,
        weekly_df: pd.DataFrame,
        benchmark_weekly_df: pd.DataFrame,
    ) -> tuple[float | None, bool]:
        if benchmark_weekly_df.empty:
            return None, False

        merged = pd.merge(
            weekly_df[["date", "close"]],
            benchmark_weekly_df[["date", "close"]],
            on="date",
            how="inner",
            suffixes=("_stock", "_benchmark"),
        )
        if len(merged) < 53:
            return None, False

        mansfield_series = self.weinstein.calc_mansfield_rs(
            merged["close_stock"],
            merged["close_benchmark"],
        )
        latest = mansfield_series.iloc[-1]
        if pd.isna(latest):
            return None, False
        latest_value = float(latest * 100)
        return latest_value, latest_value > 0

    def _calculate_core_score(
        self,
        *,
        weeks_since_stage2_start: int,
        stage_window_weeks: int,
        ma30w_slope_pct: float,
        distance_to_30w_pct: float | None,
        max_distance_to_30w_pct: float,
    ) -> float:
        freshness_score = max(0.0, (stage_window_weeks - weeks_since_stage2_start + 1) / stage_window_weeks) * 25
        slope_score = min(max(ma30w_slope_pct, 0.0), 3.0) / 3.0 * 20
        if distance_to_30w_pct is None:
            distance_score = 0.0
        else:
            normalized = max(0.0, 1.0 - min(abs(distance_to_30w_pct), max_distance_to_30w_pct) / max_distance_to_30w_pct)
            distance_score = normalized * 15
        return round(freshness_score + slope_score + distance_score, 2)

    def _rank_results(self, matches: list[dict]) -> list[dict]:
        ranked = sorted(
            matches,
            key=lambda item: (
                -item["score"],
                item["weeks_since_stage2_start"] if item["weeks_since_stage2_start"] is not None else 999,
                -(item["mansfield_rs"] or -999),
                item["ticker"],
            ),
        )
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
        return ranked

    def _build_summary_payload(self, matches: list[dict], summary_counter: dict[str, int]) -> dict:
        sector_counter = Counter()
        industry_counter = Counter()
        score_buckets = Counter()

        for item in matches:
            sector_counter[item.get("sector") or "미분류"] += 1
            industry_counter[item.get("industry") or "미분류"] += 1
            score = float(item.get("score", 0))
            if score >= 90:
                score_buckets["90+"] += 1
            elif score >= 80:
                score_buckets["80-89"] += 1
            elif score >= 70:
                score_buckets["70-79"] += 1
            else:
                score_buckets["60-69"] += 1

        return {
            "sector_counts": [
                {"name": name, "count": count}
                for name, count in sector_counter.most_common(8)
            ],
            "industry_counts": [
                {"name": name, "count": count}
                for name, count in industry_counter.most_common(8)
            ],
            "score_buckets": [
                {"name": name, "count": count}
                for name, count in score_buckets.items()
            ],
            "excluded_instruments": summary_counter["excluded_instruments"],
            "insufficient_data": summary_counter["insufficient_data"],
            "filtered_out": summary_counter["filtered_out"],
            "total_evaluated": summary_counter["total_evaluated"],
        }

    def _weekly_rows_to_dataframe(self, rows: list) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            [
                {
                    "date": row.week_start,
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                }
                for row in rows
            ]
        )
        return frame.sort_values("date").reset_index(drop=True)

    def _daily_rows_to_dataframe(self, rows: list) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            [
                {
                    "date": row.date,
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                }
                for row in rows
            ]
        )
        return frame.sort_values("date").reset_index(drop=True)

    def is_excluded_instrument(self, name: str | None) -> bool:
        if not name:
            return False

        normalized = name.strip().upper()
        if any(pattern in normalized for pattern in ETF_NAME_PATTERNS):
            return True
        if "ETN" in normalized or "스팩" in name:
            return True
        if PREFERRED_SUFFIX_PATTERN.search(name):
            return True
        return False


screener_service = ScreenerService()
