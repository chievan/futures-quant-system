from __future__ import annotations
import asyncio
import logging

from app.celery_app import celery_app
from app.services.data_service import DataService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=3600)
def download_data(self, symbol: str, granularity: str,
                  start_date: str, end_date: str, task_id: str = None):
    """Celery task for downloading market data via backtest loop."""
    try:
        service = DataService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bars = loop.run_until_complete(
            service.download_symbol(symbol, granularity, start_date, end_date, task_id)
        )
        loop.close()
        return {"status": "completed", "bars": bars}
    except Exception as e:
        logger.exception(f"Download failed for {symbol}")
        self.retry(exc=e)
