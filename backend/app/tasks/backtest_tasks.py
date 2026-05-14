from __future__ import annotations
import asyncio
import json
import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.database import async_session_factory
from app.models.backtest_task import BacktestTask
from app.services.backtest_service import BacktestService, ResearchService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=7200)
def run_single_backtest(self, task_id: str, strategy_name: str,
                        params: dict, symbol: str,
                        start_date: str, end_date: str):
    """Run a single backtest."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            BacktestService.run_backtest(task_id, strategy_name, params, symbol, start_date, end_date)
        )
        loop.close()
        return {"status": "completed", "task_id": task_id}
    except Exception as e:
        logger.exception(f"Backtest failed for task {task_id}")
        raise


@celery_app.task(bind=True, max_retries=1, soft_time_limit=86400)
def run_parameter_search(self, strategy_type: str, param_ranges: dict,
                         symbol: str, start_date: str, end_date: str,
                         parent_task_id: str = None):
    """Generate parameter combinations and run backtests for each."""
    import uuid

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    combos = loop.run_until_complete(
        ResearchService.generate_combinations(strategy_type, param_ranges)
    )

    results = []
    total = len(combos)
    for i, params in enumerate(combos):
        child_task_id = str(uuid.uuid4())

        # Create child task record
        async def _create_task():
            async with async_session_factory() as session:
                bt = BacktestTask(
                    task_id=child_task_id,
                    strategy_id=0,
                    params=json.dumps(params),
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    status="pending",
                )
                session.add(bt)
                await session.commit()
        loop.run_until_complete(_create_task())

        # Run backtest
        loop.run_until_complete(
            BacktestService.run_backtest(
                child_task_id, strategy_type, params, symbol, start_date, end_date
            )
        )

        # Collect result
        async def _get_result():
            async with async_session_factory() as session:
                stmt = select(BacktestTask).where(BacktestTask.task_id == child_task_id)
                result = await session.execute(stmt)
                t = result.scalar_one_or_none()
                if t:
                    return {
                        "task_id": child_task_id,
                        "params": params,
                        "total_return": t.total_return,
                        "sharpe_ratio": t.sharpe_ratio,
                        "max_drawdown": t.max_drawdown,
                        "win_rate": t.win_rate,
                    }
                return {"task_id": child_task_id, "params": params, "error": "not found"}
        result = loop.run_until_complete(_get_result())
        results.append(result)

        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": total, "results": results},
        )

    loop.close()

    # Sort results by Sharpe ratio
    results.sort(key=lambda r: r.get("sharpe_ratio", 0) or 0, reverse=True)
    return {"status": "completed", "total": total, "results": results}
