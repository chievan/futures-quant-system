from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.contract import ContractMeta
from app.models.download_task import DownloadTask
from app.services.tq_engine import TqEngine

logger = logging.getLogger(__name__)
settings = get_settings()

GRANULARITY_MAP = {
    "tick": 0,
    "1min": 60,
    "5min": 300,
    "15min": 900,
    "30min": 1800,
    "60min": 3600,
    "day": 86400,
}
GRANULARITY_INFLUX = {
    "tick": "tick",
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "60min": "60min",
    "day": "day",
}


class DataService:
    """Persist market data via backtest loop (no DataDownloader)."""

    @staticmethod
    def _get_influx_client() -> InfluxDBClient:
        return InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )

    async def download_symbol(self, symbol: str, granularity: str,
                              start_date: str, end_date: str,
                              task_id: Optional[str] = None) -> int:
        """Download kline data by running a backtest loop. Returns number of bars."""
        g = GRANULARITY_MAP.get(granularity)
        if g is None:
            raise ValueError(f"Unsupported granularity: {granularity}")

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        engine = TqEngine(mode="backtest", start_dt=start_dt, end_dt=end_dt)
        api = engine.api

        # Subscribe to main contract kline
        kline = api.get_kline_serial(symbol, g, data_length=5000)

        influx = self._get_influx_client()
        write_api = influx.write_api(write_options=SYNCHRONOUS)
        measure = GRANULARITY_INFLUX.get(granularity, "1min")

        bars = 0
        task_total = 0
        try:
            while True:
                api.wait_update()
                if api.is_changing(kline.iloc[-1]):
                    row = kline.iloc[-1]
                    point = Point(measure) \
                        .tag("symbol", symbol) \
                        .field("open", float(row["open"])) \
                        .field("high", float(row["high"])) \
                        .field("low", float(row["low"])) \
                        .field("close", float(row["close"])) \
                        .field("volume", int(row["volume"])) \
                        .field("open_oi", int(row.get("open_oi", 0))) \
                        .time(datetime.fromtimestamp(row["datetime"] / 1e9))
                    write_api.write(bucket=settings.influxdb_bucket, record=point)
                    bars += 1

                if api.is_changing(kline.iloc[0]):
                    task_total = len(kline)
        finally:
            engine.close()
            write_api.close()
            influx.close()

        # Update metadata in PostgreSQL
        await self._update_contract_meta(symbol, granularity, start_date, end_date, bars)

        # Update task status if task_id provided
        if task_id:
            async with async_session_factory() as session:
                stmt = select(DownloadTask).where(DownloadTask.task_id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                if task:
                    task.status = "completed"
                    task.progress = 100.0
                    task.total_bars = bars
                    task.completed_at = datetime.now()
                    await session.commit()

        return bars

    async def _update_contract_meta(self, symbol: str, granularity: str,
                                    start_date: str, end_date: str, bars: int):
        async with async_session_factory() as session:
            stmt = select(ContractMeta).where(
                ContractMeta.symbol == symbol,
                ContractMeta.granularity == granularity,
            )
            result = await session.execute(stmt)
            meta = result.scalar_one_or_none()
            if meta:
                meta.end_date = end_date
                meta.total_bars += bars
                meta.data_points += bars
            else:
                meta = ContractMeta(
                    symbol=symbol,
                    granularity=granularity,
                    start_date=start_date,
                    end_date=end_date,
                    total_bars=bars,
                    data_points=bars,
                )
                session.add(meta)
            await session.commit()

    @staticmethod
    async def get_contracts_summary() -> list[dict]:
        async with async_session_factory() as session:
            stmt = select(ContractMeta)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "symbol": r.symbol,
                    "granularity": r.granularity,
                    "start_date": r.start_date,
                    "end_date": r.end_date,
                    "total_bars": r.total_bars,
                    "quality": r.quality,
                }
                for r in rows
            ]

    @staticmethod
    async def get_contract_info(symbol: str) -> list[dict]:
        async with async_session_factory() as session:
            stmt = select(ContractMeta).where(ContractMeta.symbol == symbol)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "symbol": r.symbol,
                    "granularity": r.granularity,
                    "start_date": r.start_date,
                    "end_date": r.end_date,
                    "total_bars": r.total_bars,
                    "quality": r.quality,
                    "missing_ranges": json.loads(r.missing_ranges) if r.missing_ranges else [],
                }
                for r in rows
            ]

    @staticmethod
    async def delete_data(symbol: str, granularity: str,
                          start_date: str, end_date: str):
        influx = DataService._get_influx_client()
        delete_api = influx.delete_api()
        measure = GRANULARITY_INFLUX.get(granularity, "1min")
        start = f"{start_date}T00:00:00Z"
        end = f"{end_date}T23:59:59Z"
        predicate = f'_measurement="{measure}" AND symbol="{symbol}"'
        delete_api.delete(start, end, predicate, bucket=settings.influxdb_bucket, org=settings.influxdb_org)
        influx.close()

        async with async_session_factory() as session:
            stmt = select(ContractMeta).where(
                ContractMeta.symbol == symbol,
                ContractMeta.granularity == granularity,
            )
            result = await session.execute(stmt)
            meta = result.scalar_one_or_none()
            if meta:
                await session.delete(meta)
            await session.commit()

    @staticmethod
    async def check_quality(symbol: str) -> list[dict]:
        """Detect missing or sparse days by querying InfluxDB."""
        from datetime import timedelta
        from collections import defaultdict

        EXPECTED_BARS = {"tick": None, "1min": 240, "5min": 48, "15min": 16,
                         "30min": 8, "60min": 4, "day": 1}
        THRESHOLD_YELLOW = 0.7  # 70% of expected
        THRESHOLD_RED = 0.4  # 40% of expected

        influx = DataService._get_influx_client()
        query_api = influx.query_api()

        issues = []
        async with async_session_factory() as session:
            stmt = select(ContractMeta).where(ContractMeta.symbol == symbol)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for meta in rows:
                g = meta.granularity
                expected = EXPECTED_BARS.get(g)
                if expected is None:
                    continue

                # Query InfluxDB: count data points per day
                measure = GRANULARITY_INFLUX.get(g, "1min")
                flux = (
                    f'from(bucket: "{settings.influxdb_bucket}") '
                    f'|> range(start: {meta.start_date}, stop: {meta.end_date}) '
                    f'|> filter(fn: (r) => r._measurement == "{measure}" and r.symbol == "{symbol}") '
                    f'|> aggregateWindow(every: 1d, fn: count) '
                    f'|> yield(name: "count")'
                )
                try:
                    tables = query_api.query(flux)
                    missing_ranges = []
                    for table in tables:
                        for record in table.records:
                            if record.get_value() is not None and int(record.get_value()) < expected * THRESHOLD_YELLOW:
                                day_str = record.get_time().strftime("%Y-%m-%d")
                                count = int(record.get_value())
                                missing_ranges.append({
                                    "date": day_str,
                                    "actual_bars": count,
                                    "expected_bars": expected,
                                    "severity": "red" if count < expected * THRESHOLD_RED else "yellow",
                                })

                    quality = "green"
                    severities = {m["severity"] for m in missing_ranges}
                    if "red" in severities:
                        quality = "red"
                    elif "yellow" in severities:
                        quality = "yellow"

                    # Update the ContractMeta
                    async with async_session_factory() as session2:
                        stmt2 = select(ContractMeta).where(
                            ContractMeta.symbol == symbol,
                            ContractMeta.granularity == g,
                        )
                        r2 = await session2.execute(stmt2)
                        meta_row = r2.scalar_one_or_none()
                        if meta_row:
                            meta_row.quality = quality
                            meta_row.missing_ranges = json.dumps(missing_ranges) if missing_ranges else None
                            await session2.commit()

                    issues.append({
                        "symbol": meta.symbol,
                        "granularity": g,
                        "quality": quality,
                        "missing_ranges": missing_ranges,
                    })
                except Exception as e:
                    logger.warning(f"Quality check query failed for {symbol}/{g}: {e}")
                    issues.append({
                        "symbol": meta.symbol,
                        "granularity": g,
                        "quality": meta.quality,
                        "missing_ranges": [],
                        "error": str(e),
                    })

        influx.close()
        return issues

    @staticmethod
    async def run_full_quality_check():
        """Run quality check on all contracts."""
        async with async_session_factory() as session:
            stmt = select(ContractMeta).distinct(ContractMeta.symbol)
            result = await session.execute(stmt)
            symbols = {r.symbol for r in result.scalars().all()}

        all_issues = {}
        for sym in symbols:
            all_issues[sym] = await DataService.check_quality(sym)
        return all_issues
