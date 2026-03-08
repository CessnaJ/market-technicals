from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
import time
from typing import Iterable

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.database import async_session_maker, engine
from app.models import OHLCDaily, OHLCWeekly, PricePreloadJob, StockMaster, Watchlist
from app.schemas import (
    PricePreloadAutoSyncResponse,
    PricePreloadFailure,
    PricePreloadRunItem,
    PricePreloadRunResponse,
    PricePreloadSeedResponse,
    PricePreloadStatusResponse,
)
from app.services.data_service import data_service
from app.services.kis_api.price import kis_price_service
from app.services.stock_master_service import stock_master_service

logger = logging.getLogger(__name__)

DEFAULT_PRELOAD_STATUSES = ["PENDING", "FAILED"]
MAX_PRELOAD_ATTEMPTS = 3
PROCESSING_STALE_MINUTES = 30
PRELOAD_LOCK_KEY_1 = 31415
PRELOAD_LOCK_KEY_2 = 27182


class PreloadService:
    def __init__(self):
        self._background_task: asyncio.Task | None = None
        self._background_lock = asyncio.Lock()
        self._lock_connection: AsyncConnection | None = None
        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None

    def is_running(self) -> bool:
        return self._background_task is not None and not self._background_task.done()

    async def _acquire_runner_lock(self) -> bool:
        if self._lock_connection is not None:
            return True

        connection = await engine.connect()
        try:
            acquired = await connection.scalar(
                text("select pg_try_advisory_lock(:key1, :key2)"),
                {
                    "key1": PRELOAD_LOCK_KEY_1,
                    "key2": PRELOAD_LOCK_KEY_2,
                },
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
                {
                    "key1": PRELOAD_LOCK_KEY_1,
                    "key2": PRELOAD_LOCK_KEY_2,
                },
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
            {
                "key1": PRELOAD_LOCK_KEY_1,
                "key2": PRELOAD_LOCK_KEY_2,
            },
        )
        return bool(active)

    def _normalize_markets(self, markets: Iterable[str] | None) -> list[str]:
        normalized = [market.strip().upper() for market in (markets or []) if market and market.strip()]
        deduped: list[str] = []
        for market in normalized:
            if market not in deduped:
                deduped.append(market)
        return deduped

    def _normalize_tickers(self, tickers: Iterable[str] | None) -> list[str]:
        normalized = []
        for ticker in tickers or []:
            candidate = (ticker or "").strip().upper()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    def _format_duration(self, seconds: float | None) -> str:
        if seconds is None or seconds < 0:
            return "-"
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    async def _get_progress_snapshot(self, db: AsyncSession) -> dict[str, int]:
        total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
        pending = await db.scalar(select(func.count(PricePreloadJob.id)).where(PricePreloadJob.status == "PENDING"))
        processing = await db.scalar(select(func.count(PricePreloadJob.id)).where(PricePreloadJob.status == "PROCESSING"))
        completed = await db.scalar(select(func.count(PricePreloadJob.id)).where(PricePreloadJob.status == "COMPLETED"))
        retryable_failed = await db.scalar(
            select(func.count(PricePreloadJob.id)).where(
                PricePreloadJob.status == "FAILED",
                PricePreloadJob.attempts < MAX_PRELOAD_ATTEMPTS,
            )
        )
        terminal_failed = await db.scalar(
            select(func.count(PricePreloadJob.id)).where(
                PricePreloadJob.status == "FAILED",
                PricePreloadJob.attempts >= MAX_PRELOAD_ATTEMPTS,
            )
        )
        return {
            "total_jobs": int(total_jobs or 0),
            "pending": int(pending or 0),
            "processing": int(processing or 0),
            "completed": int(completed or 0),
            "retryable_failed": int(retryable_failed or 0),
            "terminal_failed": int(terminal_failed or 0),
        }

    async def _log_progress_summary(self, db: AsyncSession, *, event: str, batch_size: int | None = None):
        snapshot = await self._get_progress_snapshot(db)
        elapsed_seconds = (
            (datetime.now() - self._last_started_at).total_seconds()
            if self._last_started_at is not None
            else 0.0
        )
        resolved_jobs = snapshot["completed"] + snapshot["terminal_failed"]
        unresolved_jobs = snapshot["pending"] + snapshot["processing"] + snapshot["retryable_failed"]
        eta_seconds = None
        if resolved_jobs > 0 and unresolved_jobs > 0 and elapsed_seconds > 0:
            jobs_per_second = resolved_jobs / elapsed_seconds
            if jobs_per_second > 0:
                eta_seconds = unresolved_jobs / jobs_per_second

        logger.info(
            "%s total=%s completed=%s pending=%s processing=%s retryable_failed=%s terminal_failed=%s resolved=%s batch_size=%s elapsed=%s eta=%s",
            event,
            snapshot["total_jobs"],
            snapshot["completed"],
            snapshot["pending"],
            snapshot["processing"],
            snapshot["retryable_failed"],
            snapshot["terminal_failed"],
            resolved_jobs,
            batch_size if batch_size is not None else "-",
            self._format_duration(elapsed_seconds),
            self._format_duration(eta_seconds),
        )

    async def seed_universe(
        self,
        db: AsyncSession,
        *,
        target_days: int = 730,
        markets: list[str] | None = None,
        limit: int | None = None,
        reset_existing: bool = False,
    ) -> PricePreloadSeedResponse:
        normalized_markets = self._normalize_markets(markets)

        query = select(StockMaster).order_by(StockMaster.market_cap.desc(), StockMaster.ticker.asc())
        if normalized_markets:
            query = query.where(StockMaster.market.in_(normalized_markets))
        if limit:
            query = query.limit(limit)

        masters = (await db.execute(query)).scalars().all()
        if not masters:
            total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
            return PricePreloadSeedResponse(
                target_days=target_days,
                markets=normalized_markets,
                seeded=0,
                updated=0,
                skipped=0,
                total_jobs=total_jobs or 0,
            )

        tickers = [item.ticker for item in masters]
        existing_jobs_result = await db.execute(
            select(PricePreloadJob).where(PricePreloadJob.ticker.in_(tickers))
        )
        existing_jobs = {job.ticker: job for job in existing_jobs_result.scalars().all()}

        seeded = 0
        updated = 0
        skipped = 0

        for master in masters:
            priority = int(master.market_cap or 0)
            existing = existing_jobs.get(master.ticker)

            if existing is None:
                db.add(
                    PricePreloadJob(
                        ticker=master.ticker,
                        name=master.name,
                        market=master.market,
                        target_days=target_days,
                        priority=priority,
                        status="PENDING",
                    )
                )
                seeded += 1
                continue

            changed = False
            if existing.name != master.name:
                existing.name = master.name
                changed = True
            if existing.market != master.market:
                existing.market = master.market
                changed = True
            if existing.priority != priority:
                existing.priority = priority
                changed = True
            if existing.target_days != target_days:
                existing.target_days = target_days
                existing.status = "PENDING"
                changed = True
            if reset_existing:
                existing.status = "PENDING"
                existing.attempts = 0
                existing.daily_records = 0
                existing.weekly_records = 0
                existing.last_synced_from = None
                existing.last_synced_to = None
                existing.last_run_at = None
                existing.started_at = None
                existing.finished_at = None
                existing.last_error = None
                changed = True

            if changed:
                updated += 1
            else:
                skipped += 1

        await db.commit()
        total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
        return PricePreloadSeedResponse(
            target_days=target_days,
            markets=normalized_markets,
            seeded=seeded,
            updated=updated,
            skipped=skipped,
            total_jobs=total_jobs or 0,
        )

    async def seed_tickers(
        self,
        db: AsyncSession,
        *,
        tickers: list[str],
        target_days: int,
        reset_existing: bool = False,
    ) -> PricePreloadSeedResponse:
        normalized_tickers = self._normalize_tickers(tickers)
        if not normalized_tickers:
            total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
            return PricePreloadSeedResponse(
                target_days=target_days,
                markets=[],
                seeded=0,
                updated=0,
                skipped=0,
                total_jobs=total_jobs or 0,
            )

        query = (
            select(StockMaster)
            .where(StockMaster.ticker.in_(normalized_tickers))
            .order_by(StockMaster.market_cap.desc(), StockMaster.ticker.asc())
        )
        masters = (await db.execute(query)).scalars().all()
        if not masters:
            total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
            return PricePreloadSeedResponse(
                target_days=target_days,
                markets=[],
                seeded=0,
                updated=0,
                skipped=0,
                total_jobs=total_jobs or 0,
            )

        existing_jobs_result = await db.execute(
            select(PricePreloadJob).where(PricePreloadJob.ticker.in_(normalized_tickers))
        )
        existing_jobs = {job.ticker: job for job in existing_jobs_result.scalars().all()}

        seeded = 0
        updated = 0
        skipped = 0

        for master in masters:
            priority = int(master.market_cap or 0) + 10_000_000_000_000
            existing = existing_jobs.get(master.ticker)
            if existing is None:
                db.add(
                    PricePreloadJob(
                        ticker=master.ticker,
                        name=master.name,
                        market=master.market,
                        target_days=target_days,
                        priority=priority,
                        status="PENDING",
                    )
                )
                seeded += 1
                continue

            changed = False
            if existing.name != master.name:
                existing.name = master.name
                changed = True
            if existing.market != master.market:
                existing.market = master.market
                changed = True
            if existing.priority < priority:
                existing.priority = priority
                changed = True
            if existing.target_days < target_days:
                existing.target_days = target_days
                existing.status = "PENDING"
                changed = True
            if reset_existing:
                existing.status = "PENDING"
                existing.attempts = 0
                existing.daily_records = 0
                existing.weekly_records = 0
                existing.last_synced_from = None
                existing.last_synced_to = None
                existing.last_run_at = None
                existing.started_at = None
                existing.finished_at = None
                existing.last_error = None
                changed = True

            if changed:
                updated += 1
            else:
                skipped += 1

        await db.commit()
        total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
        return PricePreloadSeedResponse(
            target_days=target_days,
            markets=[],
            seeded=seeded,
            updated=updated,
            skipped=skipped,
            total_jobs=total_jobs or 0,
        )

    async def get_status(
        self,
        db: AsyncSession,
        *,
        failure_limit: int = 10,
    ) -> PricePreloadStatusResponse:
        is_running = await self.is_global_runner_active(db)
        total_jobs = await db.scalar(select(func.count(PricePreloadJob.id)))
        status_rows = (
            await db.execute(
                select(PricePreloadJob.status, func.count(PricePreloadJob.id))
                .group_by(PricePreloadJob.status)
            )
        ).all()
        status_counts = {status: count for status, count in status_rows}

        failure_rows = (
            await db.execute(
                select(PricePreloadJob)
                .where(PricePreloadJob.status == "FAILED")
                .order_by(PricePreloadJob.updated_at.desc())
                .limit(failure_limit)
            )
        ).scalars().all()

        return PricePreloadStatusResponse(
            total_jobs=total_jobs or 0,
            status_counts=status_counts,
            recent_failures=[
                PricePreloadFailure(
                    ticker=item.ticker,
                    name=item.name,
                    attempts=item.attempts,
                    last_error=item.last_error,
                    updated_at=item.updated_at,
                )
                for item in failure_rows
            ],
            is_running=is_running,
            max_attempts=MAX_PRELOAD_ATTEMPTS,
            last_started_at=self._last_started_at,
            last_finished_at=self._last_finished_at,
        )

    async def recover_stale_processing_jobs(
        self,
        db: AsyncSession,
        *,
        stale_minutes: int = PROCESSING_STALE_MINUTES,
    ) -> int:
        cutoff = datetime.now() - timedelta(minutes=stale_minutes)
        result = await db.execute(
            update(PricePreloadJob)
            .where(
                PricePreloadJob.status == "PROCESSING",
                PricePreloadJob.started_at.is_not(None),
                PricePreloadJob.started_at < cutoff,
            )
            .values(
                status="PENDING",
                finished_at=datetime.now(),
                last_error=f"Recovered from stale PROCESSING state after {stale_minutes} minutes",
            )
        )
        await db.commit()
        recovered = result.rowcount or 0
        if recovered > 0:
            logger.warning(
                "PRELOAD_RECOVER_STALE recovered=%s stale_minutes=%s",
                recovered,
                stale_minutes,
            )
        return recovered

    async def run_batch(
        self,
        db: AsyncSession,
        *,
        batch_size: int = 25,
        markets: list[str] | None = None,
        statuses: list[str] | None = None,
        use_cache: bool = False,
        force_refresh: bool = False,
        sleep_ms: int = 100,
        bypass_runner_lock: bool = False,
    ) -> PricePreloadRunResponse:
        if not bypass_runner_lock and await self.is_global_runner_active(db):
            return PricePreloadRunResponse(
                requested=batch_size,
                processed=0,
                completed=0,
                failed=0,
                skipped=0,
                results=[],
            )

        await self.recover_stale_processing_jobs(db)

        normalized_markets = self._normalize_markets(markets)
        normalized_statuses = [status.upper() for status in (statuses or DEFAULT_PRELOAD_STATUSES)]

        query = select(PricePreloadJob).where(
            PricePreloadJob.status.in_(normalized_statuses),
            PricePreloadJob.attempts < MAX_PRELOAD_ATTEMPTS,
        )
        if normalized_markets:
            query = query.where(PricePreloadJob.market.in_(normalized_markets))
        query = query.order_by(PricePreloadJob.priority.desc(), PricePreloadJob.ticker.asc()).limit(batch_size)

        jobs = (await db.execute(query)).scalars().all()
        if not jobs:
            return PricePreloadRunResponse(
                requested=batch_size,
                processed=0,
                completed=0,
                failed=0,
                skipped=0,
                results=[],
            )

        completed = 0
        failed = 0
        skipped = 0
        results: list[PricePreloadRunItem] = []
        logger.info(
            "PRELOAD_BATCH_START requested=%s selected=%s markets=%s statuses=%s",
            batch_size,
            len(jobs),
            ",".join(normalized_markets) if normalized_markets else "ALL",
            ",".join(normalized_statuses),
        )

        for job in jobs:
            now = datetime.now()
            job_timer = time.perf_counter()
            job.status = "PROCESSING"
            job.started_at = now
            job.last_run_at = now
            job.finished_at = None
            job.attempts = (job.attempts or 0) + 1
            job.last_error = None
            await db.commit()

            try:
                result = await self._process_job(
                    db,
                    job_id=job.id,
                    use_cache=use_cache,
                    force_refresh=force_refresh,
                )
                results.append(result)
                logger.info(
                    "PRELOAD_JOB_%s ticker=%s name=%s attempt=%s target_days=%s daily_records=%s weekly_records=%s duration=%s",
                    result.status,
                    result.ticker,
                    result.name,
                    job.attempts,
                    job.target_days,
                    result.daily_records,
                    result.weekly_records,
                    self._format_duration(time.perf_counter() - job_timer),
                )
                if result.status == "COMPLETED":
                    completed += 1
                elif result.status == "FAILED":
                    failed += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.exception("❌ [%s] 선적재 배치 실패", job.ticker)
                await db.rollback()
                failed_job = await db.scalar(select(PricePreloadJob).where(PricePreloadJob.id == job.id))
                if failed_job is not None:
                    failed_job.status = "FAILED"
                    failed_job.finished_at = datetime.now()
                    failed_job.last_error = str(exc)[:500]
                    await db.commit()
                failed += 1
                results.append(
                    PricePreloadRunItem(
                        ticker=job.ticker,
                        name=job.name,
                        status="FAILED",
                        error=str(exc)[:500],
                    )
                )
                logger.error(
                    "PRELOAD_JOB_FAILED ticker=%s name=%s attempt=%s target_days=%s duration=%s error=%s",
                    job.ticker,
                    job.name,
                    job.attempts,
                    job.target_days,
                    self._format_duration(time.perf_counter() - job_timer),
                    str(exc)[:500],
                )

            if sleep_ms > 0:
                await asyncio.sleep(sleep_ms / 1000)

        await self._log_progress_summary(db, event="PRELOAD_BATCH_DONE", batch_size=batch_size)

        return PricePreloadRunResponse(
            requested=batch_size,
            processed=len(results),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    async def start_auto_sync(
        self,
        *,
        current_ticker: str | None = None,
        benchmark_ticker: str | None = None,
        sync_master: bool = True,
        batch_size: int = 25,
        sleep_ms: int = 100,
        universe_target_days: int = 730,
        major_target_days: int = 3650,
        major_limit: int = 200,
    ) -> PricePreloadAutoSyncResponse:
        async with self._background_lock:
            async with async_session_maker() as db:
                if await self.is_global_runner_active(db):
                    status = await self.get_status(db)
                    return PricePreloadAutoSyncResponse(
                        started=False,
                        already_running=True,
                        message="Universe preload is already running",
                        total_jobs=status.total_jobs,
                        major_ticker_count=0,
                        is_running=True,
                        last_started_at=self._last_started_at,
                    )

                await self.recover_stale_processing_jobs(db)

            acquired = await self._acquire_runner_lock()
            if not acquired:
                async with async_session_maker() as db:
                    status = await self.get_status(db)
                return PricePreloadAutoSyncResponse(
                    started=False,
                    already_running=True,
                    message="Universe preload is already running",
                    total_jobs=status.total_jobs,
                    major_ticker_count=0,
                    is_running=True,
                    last_started_at=self._last_started_at,
                )

            try:
                async with async_session_maker() as db:
                    master_ready = await stock_master_service.is_master_ready(db)
                    if sync_master or not master_ready:
                        await stock_master_service.sync_master_data(db)

                    universe_result = await self.seed_universe(
                        db,
                        target_days=universe_target_days,
                        markets=["KOSPI", "KOSDAQ"],
                        reset_existing=False,
                    )
                    major_tickers = await self._select_major_tickers(
                        db,
                        current_ticker=current_ticker,
                        benchmark_ticker=benchmark_ticker,
                        limit=major_limit,
                    )
                    await self.seed_tickers(
                        db,
                        tickers=major_tickers,
                        target_days=major_target_days,
                        reset_existing=False,
                    )

                self._last_started_at = datetime.now()
                self._last_finished_at = None
                logger.info(
                    "PRELOAD_AUTO_SYNC_STARTED total_jobs=%s universe_target_days=%s major_target_days=%s major_ticker_count=%s batch_size=%s sleep_ms=%s current_ticker=%s benchmark_ticker=%s",
                    universe_result.total_jobs,
                    universe_target_days,
                    major_target_days,
                    len(major_tickers),
                    batch_size,
                    sleep_ms,
                    (current_ticker or "-").upper(),
                    (benchmark_ticker or "-").upper(),
                )
                self._background_task = asyncio.create_task(
                    self._run_auto_sync_loop(
                        batch_size=batch_size,
                        sleep_ms=sleep_ms,
                    )
                )

                return PricePreloadAutoSyncResponse(
                    started=True,
                    already_running=False,
                    message="Universe preload started",
                    total_jobs=universe_result.total_jobs,
                    major_ticker_count=len(major_tickers),
                    is_running=True,
                    last_started_at=self._last_started_at,
                )
            except Exception:
                await self._release_runner_lock()
                raise

    async def _select_major_tickers(
        self,
        db: AsyncSession,
        *,
        current_ticker: str | None,
        benchmark_ticker: str | None,
        limit: int,
    ) -> list[str]:
        top_rows = (
            await db.execute(
                select(StockMaster.ticker)
                .where(StockMaster.market.in_(["KOSPI", "KOSDAQ"]))
                .order_by(StockMaster.market_cap.desc(), StockMaster.ticker.asc())
                .limit(limit)
            )
        ).all()
        watchlist_rows = (await db.execute(select(Watchlist.ticker))).all()

        major_tickers: list[str] = []
        for source in [
            [row[0] for row in top_rows],
            [row[0] for row in watchlist_rows],
            [current_ticker or "", benchmark_ticker or ""],
        ]:
            for ticker in source:
                normalized = (ticker or "").strip().upper()
                if normalized and normalized not in major_tickers:
                    major_tickers.append(normalized)
        return major_tickers

    async def _run_auto_sync_loop(
        self,
        *,
        batch_size: int,
        sleep_ms: int,
    ) -> None:
        try:
            while True:
                async with async_session_maker() as db:
                    result = await self.run_batch(
                        db,
                        batch_size=batch_size,
                        statuses=DEFAULT_PRELOAD_STATUSES,
                        use_cache=False,
                        force_refresh=False,
                        sleep_ms=sleep_ms,
                        bypass_runner_lock=True,
                    )
                if result.processed == 0:
                    break
                await asyncio.sleep(0.25)
        except Exception:
            logger.exception("❌ Universe preload background loop failed")
        finally:
            self._last_finished_at = datetime.now()
            async with async_session_maker() as db:
                await self._log_progress_summary(db, event="PRELOAD_AUTO_SYNC_FINISHED")
            self._background_task = None
            await self._release_runner_lock()

    async def _process_job(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        use_cache: bool,
        force_refresh: bool,
    ) -> PricePreloadRunItem:
        job = await db.scalar(select(PricePreloadJob).where(PricePreloadJob.id == job_id))
        if job is None:
            return PricePreloadRunItem(
                ticker="UNKNOWN",
                name="UNKNOWN",
                status="SKIPPED",
                error="Job not found",
            )

        master = await db.scalar(select(StockMaster).where(StockMaster.ticker == job.ticker))
        current_price = await kis_price_service.get_current_price(job.ticker)
        name = (current_price or {}).get("name") or (master.name if master else job.name)
        market = (current_price or {}).get("market") or (master.market if master else job.market)

        if not name:
            job.status = "FAILED"
            job.finished_at = datetime.now()
            job.last_error = "Current price lookup failed"
            await db.commit()
            return PricePreloadRunItem(
                ticker=job.ticker,
                name=job.name,
                status="FAILED",
                error=job.last_error,
            )

        stock = await data_service.get_or_create_stock(
            db,
            ticker=job.ticker,
            name=name,
            market=market,
        )
        stock.name = name
        stock.market = market
        if master is not None:
            stock.sector = master.sector_name
            stock.industry = master.industry_name or (current_price or {}).get("industry_name")
        elif current_price is not None:
            stock.industry = stock.industry or current_price.get("industry_name")

        start_date = date.today() - timedelta(days=job.target_days)
        daily_data = await kis_price_service.get_daily_price(
            ticker=job.ticker,
            start_date=start_date,
            use_cache=use_cache and not force_refresh,
        )
        if not daily_data:
            job.status = "FAILED"
            job.finished_at = datetime.now()
            job.last_error = "No daily OHLCV data returned"
            await db.commit()
            return PricePreloadRunItem(
                ticker=job.ticker,
                name=name,
                status="FAILED",
                error=job.last_error,
            )

        await data_service.save_ohlcv_daily(
            db,
            stock.id,
            daily_data,
            overwrite=force_refresh,
        )
        await data_service.convert_daily_to_weekly(db, stock.id)

        daily_records = await db.scalar(
            select(func.count(OHLCDaily.id)).where(OHLCDaily.stock_id == stock.id)
        )
        weekly_records = await db.scalar(
            select(func.count(OHLCWeekly.id)).where(OHLCWeekly.stock_id == stock.id)
        )

        def _to_date(value: str | date) -> date:
            if isinstance(value, date):
                return value
            return date.fromisoformat(value)

        job.name = name
        job.market = market
        job.status = "COMPLETED"
        job.finished_at = datetime.now()
        job.daily_records = int(daily_records or 0)
        job.weekly_records = int(weekly_records or 0)
        job.last_synced_from = _to_date(daily_data[0]["date"])
        job.last_synced_to = _to_date(daily_data[-1]["date"])
        job.last_error = None
        await db.commit()

        return PricePreloadRunItem(
            ticker=job.ticker,
            name=name,
            status="COMPLETED",
            daily_records=job.daily_records,
            weekly_records=job.weekly_records,
        )


preload_service = PreloadService()
