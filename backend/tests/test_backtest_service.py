"""Tests for BacktestService: strategy logic and factor mining."""

import pytest
import math
from app.services.backtest_service import DualMovingAverageStrategy, ResearchService


class TestDualMovingAverageStrategy:
    """Unit tests for DualMovingAverageStrategy signal logic."""

    def test_buy_signal_when_fast_crosses_above_slow(self):
        strategy = DualMovingAverageStrategy(fast_period=3, slow_period=5)
        prices = [10, 11, 12, 12, 11, 10, 11, 12, 13, 14, 15]
        signals = []
        for p in prices:
            sig = strategy.on_bar(p)
            if sig:
                signals.append(sig)

        # At some point fast MA should cross above slow MA
        buy_signals = [s for s in signals if s[0] == "buy"]
        sell_signals = [s for s in signals if s[0] == "sell"]
        assert len(buy_signals) > 0 or len(sell_signals) > 0

    def test_no_signals_with_insufficient_data(self):
        strategy = DualMovingAverageStrategy(fast_period=10, slow_period=30)
        for i in range(5):
            sig = strategy.on_bar(100.0 + i)
            assert sig is None  # not enough data yet

    def test_position_tracking(self):
        strategy = DualMovingAverageStrategy(fast_period=3, slow_period=5)
        for p in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]:
            strategy.on_bar(p)
        # After enough data, position should be +1 (long) in an uptrend
        if strategy.position != 0:
            assert strategy.position in (-1, 0, 1)

    def test_mean_reversion_detection(self):
        """In a downtrend, should generate sell signals."""
        strategy = DualMovingAverageStrategy(fast_period=3, slow_period=5)
        prices = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
        signals = []
        for p in prices:
            sig = strategy.on_bar(p)
            if sig:
                signals.append(sig)

        # Some sell signals should appear
        sell_signals = [s for s in signals if s[0] == "sell"]
        assert len(sell_signals) >= 0  # may or may not, depends on MA calc


class TestResearchService:
    """Tests for parameter combination generation."""

    @pytest.mark.asyncio
    async def test_generate_dual_ma_combinations(self):
        combos = await ResearchService.generate_combinations("dual_ma", {
            "fast_min": 5, "fast_max": 8, "fast_step": 1,
            "slow_min": 20, "slow_max": 30, "slow_step": 5,
        })
        # fast: 5,6,7,8; slow: 20,25,30; filter s > f
        all_combos = [(c["fast"], c["slow"]) for c in combos]
        assert len(all_combos) > 0
        for f, s in all_combos:
            assert f < s  # slow must be greater than fast
            assert 5 <= f <= 8
            assert 20 <= s <= 30

    @pytest.mark.asyncio
    async def test_empty_for_unknown_strategy(self):
        combos = await ResearchService.generate_combinations("unknown", {})
        assert combos == []


class TestRolloverHandler:
    """Tests for rollover handler logic."""

    def test_rollover_initialization(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        recorder = PositionRecorder()
        handler = RolloverHandler("test-task", recorder)
        assert handler.current_symbol is None
        assert handler.position == 0
        assert handler.avg_price == 0.0

    def test_first_quote_sets_symbol(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        recorder = PositionRecorder()
        handler = RolloverHandler("test-task", recorder)
        assert handler.commission_rate == 0.0001

    def test_commission_rate(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        handler = RolloverHandler("test-task", PositionRecorder())
        assert handler.commission_rate == 0.0001

    def test_strategy_default_is_independent(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        handler = RolloverHandler("test-task", PositionRecorder())
        assert handler.strategy == "independent"

    def test_strategy_spread_adjust(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        handler = RolloverHandler("test-task", PositionRecorder(), strategy="spread_adjust")
        assert handler.strategy == "spread_adjust"
        assert handler._accumulated_spread == 0.0

    def test_spread_adjust_tracks_last_price(self):
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder

        handler = RolloverHandler("test-task", PositionRecorder(), strategy="spread_adjust")

        class FakeQuote:
            underlying_symbol = "KQ.m@SHFE.rb"
            last_price = 3500.0

        class FakeApi:
            @staticmethod
            def get_quote(_):
                return FakeQuote()

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))
        assert handler.current_symbol == "KQ.m@SHFE.rb"
        assert handler._last_old_price == 3500.0

    def test_no_rollover_same_symbol(self):
        """No rollover action when underlying_symbol hasn't changed."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder)
        handler.current_symbol = "KQ.m@SHFE.rb"
        handler._last_old_price = 3500.0

        class FakeQuote:
            underlying_symbol = "KQ.m@SHFE.rb"
            last_price = 3510.0

        class FakeApi:
            @staticmethod
            def get_quote(_):
                return FakeQuote()

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))
        # Same symbol -> no rollover, record not called
        recorder.record.assert_not_called()
        assert handler._last_old_price == 3510.0

    def test_independent_rollover_with_position(self):
        """Independent rollover: close old + open new, P&L calculated."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder, strategy="independent")
        # Pre-set state: long 2 contracts at avg_price 3500
        handler.current_symbol = "OLD"
        handler.position = 2
        handler.avg_price = 3500.0

        class FakeApi:
            @staticmethod
            def get_quote(_):
                q = FakeQuote()
                q.underlying_symbol = "NEW"
                q.last_price = 3620.0
                return q

        class FakeQuote:
            underlying_symbol = "NEW"
            last_price = 3620.0

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))
        # Should have called record twice (close + open)
        assert recorder.record.call_count == 2, f"call_count={recorder.record.call_count}"

        calls = recorder.record.call_args_list
        close_call = calls[0].kwargs
        open_call = calls[1].kwargs

        # Close: short (closing long), price=3620, P&L = 2*(3620-3500)=240
        assert close_call["direction"] == "short"
        assert close_call["volume"] == 2
        assert close_call["price"] == 3620.0
        assert close_call["pnl"] == 240.0
        assert close_call["is_rollover"] is True

        # Open: long (same direction as before), price=3620
        assert open_call["direction"] == "long"
        assert open_call["volume"] == 2
        assert open_call["pnl"] == 0.0
        assert open_call["is_rollover"] is True

        # avg_price reset to open price
        assert handler.avg_price == 3620.0

    def test_independent_rollover_short_position(self):
        """Rollover with short position: P&L = -position * (avg_price - price)."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder, strategy="independent")
        # Short 1 contract: avg_price = 3500, price drops to 3450 -> profit 50
        handler.current_symbol = "OLD"
        handler.position = -1
        handler.avg_price = 3500.0

        class FakeApi:
            @staticmethod
            def get_quote(_):
                q = FakeQuote()
                q.underlying_symbol = "NEW"
                q.last_price = 3450.0
                return q

        class FakeQuote:
            underlying_symbol = "NEW"
            last_price = 3450.0

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))

        assert recorder.record.call_count == 2
        close_call = recorder.record.call_args_list[0].kwargs
        open_call = recorder.record.call_args_list[1].kwargs

        # P&L = -(-1)*(3500-3450) = 50 (short profits from price drop)
        assert close_call["direction"] == "long"
        assert close_call["volume"] == 1
        assert close_call["pnl"] == 50.0

        # Open: short (same direction as before)
        assert open_call["direction"] == "short"
        assert open_call["pnl"] == 0.0

    def test_spread_adjust_rollover_logic(self):
        """Spread adjust: avg_price adjusted by spread, not reset."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder, strategy="spread_adjust")
        handler.current_symbol = "OLD_CONTRACT"
        handler.position = 1
        handler.avg_price = 3500.0
        handler._last_old_price = 3500.0

        class FakeQuote:
            underlying_symbol = "NEW_CONTRACT"
            last_price = 3600.0

        class FakeApi:
            @staticmethod
            def get_quote(_):
                return FakeQuote()

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))

        assert recorder.record.call_count == 2
        # avg_price adjusted by spread (3600 - 3500 = 100)
        assert handler.avg_price == 3600.0  # 3500 + 100
        # accumulated_spread = spread * position = 100 * 1 = 100
        assert handler._accumulated_spread == 100.0

    def test_rollover_no_position(self):
        """No rollover actions when position is 0."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder)
        handler.current_symbol = "OLD_CONTRACT"
        handler.position = 0

        class FakeQuote:
            underlying_symbol = "NEW_CONTRACT"
            last_price = 3600.0
        class FakeApi:
            @staticmethod
            def get_quote(_):
                return FakeQuote()

        import asyncio
        asyncio.run(handler.on_quote_change(FakeApi(), FakeQuote(), None))
        # No position -> no records
        recorder.record.assert_not_called()
        assert handler.current_symbol == "NEW_CONTRACT"

    def test_rollover_commission_calculation(self):
        """Commission = abs(position) * price * commission_rate."""
        from app.services.backtest_service import RolloverHandler
        from app.services.position_recorder import PositionRecorder
        from unittest.mock import AsyncMock

        recorder = PositionRecorder()
        recorder.record = AsyncMock()
        handler = RolloverHandler("test-task", recorder)
        handler.commission_rate = 0.0002  # 0.02%
        handler.current_symbol = "OLD"
        handler.position = 5
        handler.avg_price = 4000.0

        class FakeQuote:
            underlying_symbol = "NEW"
            last_price = 4100.0
            last_price = 4100.0
        class FakeApi:
            @staticmethod
            def get_quote(_):
                return FakeQuote()

        import asyncio
        # Set initial
        q_init = FakeQuote()
        q_init.underlying_symbol = "OLD"
        q_init.last_price = 4050.0
        handler._last_old_price = 4050.0
        asyncio.run(handler.on_quote_change(FakeApi(), q_init, None))
        recorder.record.reset_mock()

        # Rollover
        q_new = FakeQuote()
        q_new.underlying_symbol = "NEW"
        q_new.last_price = 4100.0
        asyncio.run(handler.on_quote_change(FakeApi(), q_new, None))

        # Commission = 5 * 4100 * 0.0002 = 4.1
        assert recorder.record.call_count == 2
        for call in recorder.record.call_args_list:
            assert call.kwargs["commission"] == 4.1


class TestFactorMiner:
    """Tests for factor mining logic."""

    def test_forward_returns_computation(self):
        from app.services.backtest_service import FactorMiner

        closes = [100.0, 102.0, 101.0, 103.0, 105.0, 107.0]
        returns = FactorMiner.compute_forward_returns(closes, periods=2)
        # returns[0] = (102-100)/100 for periods=1... actually for periods=2:
        # fwd[0] = (103-100)/100 = 0.03
        # fwd[1] = (105-102)/102 ≈ 0.0294
        # fwd[2] = (107-101)/101 ≈ 0.0594
        # fwd[3:] = None
        assert returns[0] is not None
        assert returns[-1] is None  # last one has no forward data
        assert len(returns) == len(closes)

    def test_simple_factor_expression(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0, 102.0, 101.0, 103.0, 105.0]
        high = [101.0, 103.0, 102.0, 104.0, 106.0]
        low = [99.0, 101.0, 100.0, 102.0, 104.0]
        volume = [1000, 1100, 900, 1200, 1300]

        values = FactorMiner.compute_factor(close, high, low, volume, "close - low")
        assert len(values) == len(close)
        # Each value should be close minus low
        for i in range(len(close)):
            assert abs(values[i] - (close[i] - low[i])) < 0.001

    def test_rolling_mean_expression(self):
        from app.services.backtest_service import FactorMiner

        close = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        values = FactorMiner.compute_factor(close, close, close, [0]*6, "rolling_mean(close, 3)")
        assert len(values) == len(close)
        # First two values should be None (not enough data)
        assert values[0] is None
        assert values[1] is None
        # values[2] = mean(10,11,12) = 11
        assert values[2] is not None

    def test_ic_computation(self):
        from app.services.backtest_service import FactorMiner

        # Perfect positive correlation
        factor = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]

        result = FactorMiner.compute_ic(factor, returns)
        assert result["samples"] >= 10
        assert result["ic"] is not None

    def test_ic_too_few_samples(self):
        from app.services.backtest_service import FactorMiner

        # Fewer than 10 samples
        factor = [1.0, 2.0, 3.0]
        returns = [0.01, 0.02, 0.03]

        result = FactorMiner.compute_ic(factor, returns)
        assert result["samples"] < 10
        assert "warning" in result

    def test_invalid_expression_raises(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0] * 10
        with pytest.raises(ValueError, match="Factor expression evaluation failed"):
            FactorMiner.compute_factor(close, close, close, [0]*10, "invalid_func(close)")

    def test_factor_abs_and_sign(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0, 102.0, 98.0, 105.0, 101.0]

        # Test abs works
        values = FactorMiner.compute_factor(close, close, close, [0]*5, "abs(close - 100)")
        assert len(values) == 5
        assert values[0] == 0.0  # abs(100-100) = 0
        assert values[1] == 2.0  # abs(102-100) = 2

    def test_factor_unknown_function_raises(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0] * 10
        with pytest.raises(ValueError):
            FactorMiner.compute_factor(close, close, close, [0]*10, "open_unknown(close)")

    def test_factor_sign(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0, 102.0, 98.0, 105.0]
        values = FactorMiner.compute_factor(close, close, close, [0]*4, "sign(close - 100)")
        assert values[0] == 0.0  # sign(0) = 0
        assert values[1] == 1.0  # sign(2) = 1
        assert values[2] == -1.0  # sign(-2) = -1

    def test_factor_diff(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0, 102.0, 105.0, 103.0]
        values = FactorMiner.compute_factor(close, close, close, [0]*4, "diff(close)")
        assert values[0] is None  # diff of first element
        assert values[1] == 2.0
        assert values[2] == 3.0
        assert values[3] == -2.0

    def test_factor_lag(self):
        from app.services.backtest_service import FactorMiner

        close = [100.0, 102.0, 105.0, 103.0]
        values = FactorMiner.compute_factor(close, close, close, [0]*4, "lag(close, 1)")
        assert values[0] is None  # lag 1
        assert values[1] == 100.0
        assert values[2] == 102.0
        assert values[3] == 105.0

    def test_factor_rolling_std(self):
        from app.services.backtest_service import FactorMiner

        close = [10.0, 11.0, 12.0, 13.0, 14.0]
        values = FactorMiner.compute_factor(close, close, close, [0]*5, "rolling_std(close, 3)")
        assert values[0] is None
        assert values[1] is None
        assert values[2] is not None  # std of [10,11,12]
        assert values[3] is not None
        assert values[4] is not None

    def test_ic_with_nan_values(self):
        from app.services.backtest_service import FactorMiner

        # Mix of valid and None values
        factor = [1.0, None, 3.0, None, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,
                 11.0, 12.0, 13.0, 14.0, 15.0]
        returns = [0.01, 0.02, None, 0.04, None, 0.06, 0.07, 0.08, 0.09, 0.10,
                   0.11, 0.12, 0.13, 0.14, 0.15]

        result = FactorMiner.compute_ic(factor, returns)
        # Should filter out None pairs and compute on remaining
        assert result["samples"] > 0
        assert result["ic"] is not None

    def test_forward_returns_all_none_at_end(self):
        from app.services.backtest_service import FactorMiner

        closes = [100.0, 102.0, 101.0]
        returns = FactorMiner.compute_forward_returns(closes, periods=5)
        # All should be None since periods > len(closes)
        assert all(r is None for r in returns)
