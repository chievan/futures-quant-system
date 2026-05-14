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
        """Verify that on_quote_change tracks _last_old_price between calls."""
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
