from __future__ import annotations
from typing import Optional
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.database import async_session_factory
from app.models.backtest_task import BacktestTask
from app.services.backtest_service import ResearchService, FactorMiner
from app.tasks.backtest_tasks import run_single_backtest, run_parameter_search

router = APIRouter(prefix="/api/research", tags=["research"])


class SingleBacktestRequest(BaseModel):
    strategy_id: int
    params: dict
    symbol: str
    start_date: str
    end_date: str


class ParameterSearchRequest(BaseModel):
    strategy_type: str = "dual_ma"
    param_ranges: dict
    symbol: str
    start_date: str
    end_date: str


@router.post("/backtest")
async def submit_single_backtest(req: SingleBacktestRequest):
    """Submit a single backtest task."""
    task_id = str(uuid.uuid4())

    async with async_session_factory() as session:
        bt = BacktestTask(
            task_id=task_id,
            strategy_id=req.strategy_id,
            params=json.dumps(req.params),
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            status="pending",
        )
        session.add(bt)
        await session.commit()

    run_single_backtest.delay(
        task_id, f"strategy_{req.strategy_id}", req.params,
        req.symbol, req.start_date, req.end_date,
    )
    return {"task_id": task_id, "status": "pending"}


@router.post("/search")
async def submit_parameter_search(req: ParameterSearchRequest):
    """Submit a parameter search task (generates combinations, runs all backtests)."""
    parent_task_id = str(uuid.uuid4())

    # Create parent task record
    async with async_session_factory() as session:
        bt = BacktestTask(
            task_id=parent_task_id,
            strategy_id=0,
            params=json.dumps(req.param_ranges),
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            status="pending",
        )
        session.add(bt)
        await session.commit()

    run_parameter_search.delay(
        req.strategy_type, req.param_ranges, req.symbol,
        req.start_date, req.end_date, parent_task_id,
    )
    return {"task_id": parent_task_id, "status": "pending"}


@router.get("/tasks")
async def list_research_tasks(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """List all backtest/research tasks."""
    async with async_session_factory() as session:
        stmt = select(BacktestTask).order_by(BacktestTask.created_at.desc())
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        count_stmt = select(BacktestTask)
        total = len((await session.execute(count_stmt)).scalars().all())

        return {
            "total": total,
            "page": page,
            "size": size,
            "tasks": [
                {
                    "id": t.id,
                    "task_id": t.task_id,
                    "strategy_id": t.strategy_id,
                    "params": t.params,
                    "symbol": t.symbol,
                    "start_date": t.start_date,
                    "end_date": t.end_date,
                    "status": t.status,
                    "progress": t.progress,
                    "total_return": t.total_return,
                    "sharpe_ratio": t.sharpe_ratio,
                    "max_drawdown": t.max_drawdown,
                    "win_rate": t.win_rate,
                    "profit_factor": t.profit_factor,
                    "total_trades": t.total_trades,
                    "error": t.error,
                    "created_at": t.created_at.isoformat(),
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in tasks
            ],
        }


@router.get("/tasks/{task_id}")
async def get_research_task(task_id: str):
    """Get details of a specific research task."""
    async with async_session_factory() as session:
        stmt = select(BacktestTask).where(BacktestTask.task_id == task_id)
        result = await session.execute(stmt)
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(404, "Task not found")

        return {
            "id": t.id,
            "task_id": t.task_id,
            "strategy_id": t.strategy_id,
            "params": t.params,
            "symbol": t.symbol,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "status": t.status,
            "progress": t.progress,
            "total_return": t.total_return,
            "sharpe_ratio": t.sharpe_ratio,
            "max_drawdown": t.max_drawdown,
            "win_rate": t.win_rate,
            "profit_factor": t.profit_factor,
            "total_trades": t.total_trades,
            "equity_curve": t.equity_curve,
            "error": t.error,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }


class FactorMiningRequest(BaseModel):
    expression: str
    close: list[float]
    high: Optional[list[float]] = None
    low: Optional[list[float]] = None
    volume: Optional[list[int]] = None
    forward_periods: int = 5


@router.post("/factor-mine")
async def factor_mining(req: FactorMiningRequest):
    """Evaluate a factor expression and compute IC/IR."""
    high = req.high or req.close
    low = req.low or req.close
    volume = req.volume or [0] * len(req.close)

    factor_values = FactorMiner.compute_factor(
        req.close, high, low, volume, req.expression,
    )
    forward_returns = FactorMiner.compute_forward_returns(
        req.close, req.forward_periods,
    )
    ic_result = FactorMiner.compute_ic(factor_values, forward_returns)

    return {
        "expression": req.expression,
        "factor_values": factor_values[:100],  # first 100 for preview
        "forward_returns": forward_returns[:100],
        "ic_analysis": ic_result,
    }
