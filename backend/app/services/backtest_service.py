from __future__ import annotations
from typing import Optional
import json
import logging
import math
from datetime import datetime
from decimal import Decimal

import pandas as pd
import numpy as np
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models.backtest_task import BacktestTask
from app.models.position import PositionChange
from app.services.tq_engine import TqEngine
from app.services.position_recorder import PositionRecorder

logger = logging.getLogger(__name__)
settings = get_settings()


class RolloverHandler:
    """Handle main contract rollover (移仓换月) for KQ.m@ symbols.

    Two strategies (set via ROLLOVER_STRATEGY env var):
      - independent (默认): close old position, open new at market price.
        Rollover generates actual close+open trades with realized P&L.
      - spread_adjust: the spread between old and new contract prices is
        treated as a one-time cost. avg_price is adjusted by the spread so
        the continuous P&L calculation remains consistent.
    """

    def __init__(self, backtest_task_id: str, recorder: PositionRecorder,
                 strategy: str = "independent"):
        self.task_id = backtest_task_id
        self.recorder = recorder
        self.current_symbol = None
        self.position = 0  # net position (+ for long, - for short)
        self.avg_price = 0.0
        self.commission_rate = 0.0001  # 0.01%
        self.strategy = strategy
        # Track last price from old contract to compute spread
        self._last_old_price: Optional[float] = None
        self._accumulated_spread: float = 0.0  # cumulative spread cost

    async def on_quote_change(self, api, quote, timestamp: datetime):
        """Detect underlying_symbol change and execute rollover."""
        new_symbol = quote.underlying_symbol
        if self.current_symbol is None:
            self.current_symbol = new_symbol
            self._last_old_price = float(quote.last_price)
            return

        if new_symbol != self.current_symbol:
            logger.info(
                f"Rollover detected: {self.current_symbol} -> {new_symbol} "
                f"at {timestamp} (strategy={self.strategy})"
            )
            if self.position != 0 and self.strategy == "independent":
                await self._independent_rollover(quote, timestamp)
            elif self.position != 0 and self.strategy == "spread_adjust":
                await self._spread_adjust_rollover(quote, timestamp)

            self.current_symbol = new_symbol
        else:
            # Track last price for spread_adjust strategy
            self._last_old_price = float(quote.last_price)

    async def _independent_rollover(self, quote, timestamp: datetime):
        """Close old position, open new at market price."""
        price = float(quote.last_price)
        commission = abs(self.position) * price * self.commission_rate
        pnl = self.position * (price - self.avg_price) if self.position > 0 else \
              -self.position * (self.avg_price - price)

        direction = "short" if self.position > 0 else "long"
        await self.recorder.record(
            backtest_task_id=self.task_id,
            timestamp=timestamp,
            symbol=self.current_symbol,
            direction=direction,
            volume=abs(self.position),
            price=price,
            pnl=round(pnl, 2),
            is_rollover=True,
            old_symbol=self.current_symbol,
            commission=round(commission, 2),
        )

        new_direction = "long" if self.position > 0 else "short"
        await self.recorder.record(
            backtest_task_id=self.task_id,
            timestamp=timestamp,
            symbol=quote.underlying_symbol,
            direction=new_direction,
            volume=abs(self.position),
            price=price,
            pnl=0.0,
            is_rollover=True,
            old_symbol=self.current_symbol,
            commission=round(commission, 2),
        )
        self.avg_price = price

    async def _spread_adjust_rollover(self, quote, timestamp: datetime):
        """Adjust avg_price by spread; record spread as a separate cost."""
        old_price = self._last_old_price or float(quote.last_price)
        new_price = float(quote.last_price)
        spread = new_price - old_price

        # Adjust avg_price by the spread to keep P&L continuous
        old_avg = self.avg_price
        if self.position > 0:
            self.avg_price += spread
        else:
            self.avg_price -= spread

        self._accumulated_spread += round(spread * abs(self.position), 2)

        commission = abs(self.position) * new_price * self.commission_rate
        close_direction = "short" if self.position > 0 else "long"
        new_direction = "long" if self.position > 0 else "short"

        # Record rollover close (P&L includes spread adjustment cost)
        await self.recorder.record(
            backtest_task_id=self.task_id,
            timestamp=timestamp,
            symbol=self.current_symbol,
            direction=close_direction,
            volume=abs(self.position),
            price=new_price,
            pnl=round(-self._accumulated_spread, 2),
            is_rollover=True,
            old_symbol=self.current_symbol,
            commission=round(commission, 2),
        )

        await self.recorder.record(
            backtest_task_id=self.task_id,
            timestamp=timestamp,
            symbol=quote.underlying_symbol,
            direction=new_direction,
            volume=abs(self.position),
            price=new_price,
            pnl=0.0,
            is_rollover=True,
            old_symbol=self.current_symbol,
            commission=round(commission, 2),
        )

        logger.info(
            f"Spread adjust rollover: spread={spread:.2f}, "
            f"avg_price {old_avg:.2f} -> {self.avg_price:.2f}, "
            f"accumulated_spread={self._accumulated_spread:.2f}"
        )


class DualMovingAverageStrategy:
    """Dual MA crossover strategy — same code for backtest / kq / live."""

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_ma: Optional[float] = None
        self.slow_ma: Optional[float] = None
        self.position = 0  # net position: -1 short, 0 flat, 1 long
        self.cache: list[float] = []

    def on_bar(self, close: float) -> Optional[tuple[str, float]]:
        """Process a new bar. Returns (signal, price) or None."""
        self.cache.append(close)
        if len(self.cache) < self.slow_period:
            return None

        df = pd.Series(self.cache)
        fast = df.rolling(self.fast_period).mean().iloc[-1]
        slow = df.rolling(self.slow_period).mean().iloc[-1]

        signal = None
        if not pd.isna(fast) and not pd.isna(slow):
            if fast > slow and self.position <= 0:
                signal = ("buy", close)
                self.position = 1
            elif fast < slow and self.position >= 0:
                signal = ("sell", close)
                self.position = -1
            elif fast <= slow and self.position > 0:
                signal = ("sell", close)
                self.position = 0
            elif fast >= slow and self.position < 0:
                signal = ("buy", close)
                self.position = 0

        self.fast_ma = float(fast) if not pd.isna(fast) else None
        self.slow_ma = float(slow) if not pd.isna(slow) else None
        return signal


class BacktestService:
    """Execute backtest for a given strategy and parameter set."""

    @staticmethod
    async def run_backtest(task_id: str, strategy_name: str, params: dict,
                           symbol: str, start_date: str, end_date: str):
        """Run a single backtest task and store results."""
        async with async_session_factory() as session:
            stmt = select(BacktestTask).where(BacktestTask.task_id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.status = "running"
            await session.commit()

        recorder = PositionRecorder()
        rollover = RolloverHandler(task_id, recorder, strategy=settings.rollover_strategy)

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            engine = TqEngine(mode="backtest", start_dt=start_dt, end_dt=end_dt)
            api = engine.api

            # Use main contract format if not explicitly a specific contract
            if not symbol.startswith("KQ.m@") and "." not in symbol:
                # Try to use main contract
                pass

            kline = api.get_kline_serial(symbol, 60, data_length=5000)

            strategy = DualMovingAverageStrategy(
                fast_period=int(params.get("fast", 10)),
                slow_period=int(params.get("slow", 30)),
            )

            equity_curve = []
            total_bars = 0

            while True:
                api.wait_update()
                if api.is_changing(kline.iloc[-1]):
                    row = kline.iloc[-1]
                    ts = datetime.fromtimestamp(row["datetime"] / 1e9)
                    close = float(row["close"])
                    signal = strategy.on_bar(close)

                    if signal:
                        action, price = signal
                        vol = 1  # 1 contract
                        direction = "long" if action == "buy" else "short"
                        pnl = 0.0
                        if action == "buy" and rollover.position < 0:
                            pnl = -rollover.position * (rollover.avg_price - price)
                        elif action == "sell" and rollover.position > 0:
                            pnl = rollover.position * (price - rollover.avg_price)

                        commission = vol * price * rollover.commission_rate
                        await recorder.record(
                            backtest_task_id=task_id,
                            timestamp=ts,
                            symbol=rollover.current_symbol or symbol,
                            direction=direction,
                            volume=vol,
                            price=price,
                            pnl=round(pnl, 2),
                            is_rollover=False,
                            commission=round(commission, 2),
                        )

                        rollover.position = strategy.position
                        rollover.avg_price = price

                    equity_curve.append({
                        "t": ts.isoformat(),
                        "close": close,
                        "fast_ma": strategy.fast_ma,
                        "slow_ma": strategy.slow_ma,
                        "position": strategy.position,
                    })
                    total_bars += 1

                # Check for rollover
                if api.is_changing(rollover) and hasattr(api, 'get_quote'):
                    try:
                        quote = api.get_quote(symbol)
                        await rollover.on_quote_change(api, quote, datetime.now())
                    except Exception:
                        pass

        except Exception as e:
            logger.exception(f"Backtest failed for task {task_id}")
            async with async_session_factory() as session:
                stmt = select(BacktestTask).where(BacktestTask.task_id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error = str(e)
                    await session.commit()
            return

        finally:
            engine.close()

        # Calculate results
        if equity_curve:
            df = pd.DataFrame(equity_curve)
            closes = df["close"].values
            returns = np.diff(closes) / closes[:-1]
            total_return = float((closes[-1] - closes[0]) / closes[0])
            sharpe = float(np.mean(returns) / np.std(returns) * math.sqrt(252)) if len(returns) > 0 and np.std(returns) > 0 else 0.0

            cumulative = np.cumprod(1 + np.append([0], returns))
            peak = np.maximum.accumulate(cumulative)
            dd = (cumulative - peak) / peak
            max_dd = float(np.min(dd))

            # Trade stats from DB
            async with async_session_factory() as session:
                count_stmt = select(PositionChange).where(
                    PositionChange.backtest_task_id == task_id,
                    PositionChange.is_rollover == False,
                )
                result = await session.execute(count_stmt)
                trades = result.scalars().all()
                wins = sum(1 for t in trades if t.pnl > 0)
                total_trades = len(trades)
                win_rate = wins / total_trades if total_trades > 0 else 0

                gains = [t.pnl for t in trades if t.pnl > 0]
                losses_list = [t.pnl for t in trades if t.pnl < 0]
                avg_win = np.mean(gains) if gains else 0
                avg_loss = abs(np.mean(losses_list)) if losses_list else 0
                profit_factor = (avg_win / avg_loss) if avg_loss > 0 else 0

            async with async_session_factory() as session:
                stmt = select(BacktestTask).where(BacktestTask.task_id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                if task:
                    task.status = "completed"
                    task.progress = 100.0
                    task.total_return = round(total_return, 4)
                    task.sharpe_ratio = round(sharpe, 4)
                    task.max_drawdown = round(max_dd, 4)
                    task.win_rate = round(win_rate, 4)
                    task.profit_factor = round(profit_factor, 2)
                    task.total_trades = total_trades
                    task.equity_curve = json.dumps(equity_curve)
                    task.completed_at = datetime.now()
                    await session.commit()

        logger.info(f"Backtest complete: task={task_id} ret={total_return:.2%} sharpe={sharpe:.2f}")


class ResearchService:
    """Parameter search and factor mining."""

    @staticmethod
    async def generate_combinations(strategy_type: str, param_ranges: dict) -> list[dict]:
        """Generate all parameter combinations within given ranges."""
        if strategy_type == "dual_ma":
            fast_range = range(
                int(param_ranges.get("fast_min", 5)),
                int(param_ranges.get("fast_max", 20)) + 1,
                int(param_ranges.get("fast_step", 1)),
            )
            slow_range = range(
                int(param_ranges.get("slow_min", 20)),
                int(param_ranges.get("slow_max", 60)) + 1,
                int(param_ranges.get("slow_step", 5)),
            )
            return [
                {"fast": f, "slow": s}
                for f in fast_range
                for s in slow_range
                if s > f
            ]
        return []


class FactorMiner:
    """Factor mining: evaluate user-defined factor expressions using IC/IR."""

    SUPPORTED_OPS = {"+", "-", "*", "/", "rolling_mean", "rolling_std", "lag", "diff", "abs", "sign"}

    @staticmethod
    def compute_factor(close: list[float], high: list[float], low: list[float],
                       volume: list[int], expression: str) -> list[Optional[float]]:
        """Evaluate a factor expression against price data.

        Expression uses 'close', 'high', 'low', 'volume' as operands and
        supports: +, -, *, /, rolling_mean(field, N), rolling_std(field, N),
        lag(field, N), diff(field), abs(field), sign(field).
        """
        import numpy as np
        import pandas as pd

        df = pd.DataFrame({
            "close": close, "high": high, "low": low, "volume": volume,
        })

        # Build safe eval namespace
        # Functions receive already-evaluated pandas Series as first arg
        namespace = {
            "close": df["close"], "high": df["high"], "low": df["low"],
            "volume": df["volume"],
            "rolling_mean": lambda s, n: s.rolling(int(n)).mean(),
            "rolling_std": lambda s, n: s.rolling(int(n)).std(),
            "lag": lambda s, n: s.shift(int(n)),
            "diff": lambda s: s.diff(),
            "abs": lambda s: np.abs(s),
            "sign": lambda s: np.sign(s),
        }

        try:
            result = eval(expression, {"__builtins__": {}}, namespace)
            return [float(v) if not pd.isna(v) else None for v in result]
        except Exception as e:
            raise ValueError(f"Factor expression evaluation failed: {e}")

    @staticmethod
    def compute_ic(factor_values: list[Optional[float]],
                   forward_returns: list[Optional[float]]) -> dict:
        """Compute Spearman rank IC and IR."""
        import numpy as np
        from scipy.stats import spearmanr

        pairs = [(f, r) for f, r in zip(factor_values, forward_returns)
                 if f is not None and r is not None and not (np.isnan(f) or np.isnan(r))]
        if len(pairs) < 10:
            return {"ic": 0.0, "ir": 0.0, "samples": len(pairs), "warning": "too few samples"}

        factors, returns = zip(*pairs)
        ic, p_value = spearmanr(factors, returns)
        ic_series = []

        # Rolling IC over windows for IR calculation
        window = min(20, len(pairs) // 4)
        for i in range(window, len(pairs)):
            f_win, r_win = factors[i - window:i], returns[i - window:i]
            ic_win, _ = spearmanr(f_win, r_win)
            ic_series.append(ic_win)

        ir = float(np.nanmean(ic_series) / np.nanstd(ic_series)) if np.nanstd(ic_series) > 0 else 0.0

        return {
            "ic": round(float(ic), 4),
            "ir": round(ir, 4),
            "p_value": round(float(p_value), 4),
            "samples": len(pairs),
        }

    @staticmethod
    def compute_forward_returns(close: list[float], periods: int = 5) -> list[Optional[float]]:
        """Compute N-period forward returns."""
        import numpy as np
        arr = np.array(close, dtype=float)
        fwd = np.full_like(arr, np.nan)
        fwd[:-periods] = (arr[periods:] - arr[:-periods]) / arr[:-periods]
        return [float(v) if not np.isnan(v) else None for v in fwd]
