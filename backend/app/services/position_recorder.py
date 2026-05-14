from __future__ import annotations
from typing import Optional
import json
import logging
from datetime import datetime

from sqlalchemy import select, func

from app.database import async_session_factory
from app.models.position import PositionChange
from app.models.backtest_task import BacktestTask

logger = logging.getLogger(__name__)


class PositionRecorder:
    """Record and query position changes during backtest or live trading."""

    @staticmethod
    async def record(
        backtest_task_id: str,
        timestamp: datetime,
        symbol: str,
        direction: str,
        volume: int,
        price: float,
        pnl: float = 0.0,
        is_rollover: bool = False,
        old_symbol: Optional[str] = None,
        commission: float = 0.0,
    ):
        async with async_session_factory() as session:
            change = PositionChange(
                backtest_task_id=backtest_task_id,
                timestamp=timestamp,
                symbol=symbol,
                direction=direction,
                volume=volume,
                price=price,
                pnl=pnl,
                is_rollover=is_rollover,
                old_symbol=old_symbol,
                commission=commission,
            )
            session.add(change)
            await session.commit()

    @staticmethod
    async def get_history(task_id: str, page: int = 1, size: int = 20) -> dict:
        async with async_session_factory() as session:
            base_stmt = select(PositionChange).where(
                PositionChange.backtest_task_id == task_id
            ).order_by(PositionChange.timestamp)

            count_stmt = select(func.count()).select_from(PositionChange).where(
                PositionChange.backtest_task_id == task_id
            )
            total = await session.scalar(count_stmt) or 0

            offset = (page - 1) * size
            stmt = base_stmt.offset(offset).limit(size)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            return {
                "total": total,
                "page": page,
                "size": size,
                "items": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat(),
                        "symbol": r.symbol,
                        "direction": r.direction,
                        "volume": r.volume,
                        "price": r.price,
                        "pnl": r.pnl,
                        "is_rollover": r.is_rollover,
                        "old_symbol": r.old_symbol,
                        "commission": r.commission,
                    }
                    for r in rows
                ],
            }

    @staticmethod
    async def get_analysis(task_id: str) -> dict:
        async with async_session_factory() as session:
            # Get all changes for this task
            stmt = select(PositionChange).where(
                PositionChange.backtest_task_id == task_id
            ).order_by(PositionChange.timestamp)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return {}

            total_pnl = sum(r.pnl for r in rows if r.pnl != 0)
            realized_pnl = sum(r.pnl for r in rows if not r.is_rollover)
            floating_pnl = total_pnl - realized_pnl

            wins = sum(1 for r in rows if r.pnl > 0)
            losses = sum(1 for r in rows if r.pnl < 0)
            total_trades = wins + losses
            win_rate = wins / total_trades if total_trades > 0 else 0

            avg_win = sum(r.pnl for r in rows if r.pnl > 0) / wins if wins > 0 else 0
            avg_loss = abs(sum(r.pnl for r in rows if r.pnl < 0) / losses) if losses > 0 else 0
            profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

            # Max drawdown from equity curve if stored in BacktestTask
            task_stmt = select(BacktestTask).where(BacktestTask.task_id == task_id)
            task_result = await session.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            max_dd = task.max_drawdown if task else None

            return {
                "total_pnl": round(total_pnl, 2),
                "realized_pnl": round(realized_pnl, 2),
                "floating_pnl": round(floating_pnl, 2),
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 2),
                "max_drawdown": round(max_dd, 4) if max_dd else None,
                "total_trades": total_trades,
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
            }

    @staticmethod
    async def export_csv(task_id: str) -> str:
        async with async_session_factory() as session:
            stmt = select(PositionChange).where(
                PositionChange.backtest_task_id == task_id
            ).order_by(PositionChange.timestamp)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            lines = ["timestamp,symbol,direction,volume,price,pnl,is_rollover,old_symbol,commission"]
            for r in rows:
                lines.append(
                    f"{r.timestamp.isoformat()},{r.symbol},{r.direction},{r.volume},"
                    f"{r.price},{r.pnl},{r.is_rollover},{r.old_symbol or ''},{r.commission}"
                )
            return "\n".join(lines)
