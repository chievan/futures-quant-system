"""Tests for TqEngine unified interface.

These tests validate the configuration logic without requiring actual
TqSdk connection (which needs a network). We test:
  - Mode detection
  - Backtest mode rejects missing dates
  - Config reads from env vars correctly
"""

import os
from datetime import datetime
import pytest

from app.config import get_settings


class TestTqEngineConfig:
    """Test TqEngine configuration without network."""

    def test_default_mode_is_backtest(self, clean_env):
        """Default TQ_MODE should be 'backtest'."""
        settings = get_settings()
        # After clean_env removes TQ_MODE, the setting should fallback
        assert settings.tq_mode == "backtest"

    def test_settings_read_env(self):
        """Settings should read from environment variables."""
        settings = get_settings()
        assert settings.tq_username == "test_user"
        assert settings.tq_password == "test_pass"
        assert settings.tq_broker == "test_broker"
        assert settings.tq_account_id == "123456"
        assert settings.tq_trade_pwd == "test_trade_pwd"

    def test_backtest_mode_requires_dates(self):
        """Backtest mode should raise ValueError if start/end not provided."""
        from app.services.tq_engine import TqEngine
        with pytest.raises(ValueError, match="start_dt and end_dt are required"):
            engine = TqEngine(mode="backtest")
            _ = engine.api  # triggers _build_api

    def test_backtest_mode_accepts_dates(self):
        """With dates provided, TqEngine should attempt connection (will fail on network).
        We just verify it doesn't raise ValueError on construction."""
        from app.services.tq_engine import TqEngine
        engine = TqEngine(
            mode="backtest",
            start_dt=datetime(2024, 1, 1),
            end_dt=datetime(2024, 1, 31),
        )
        assert engine.mode == "backtest"
        # Don't access .api — that will attempt network connection
        engine.close()

    def test_kq_mode(self):
        """KQ mode should succeed initialization."""
        from app.services.tq_engine import TqEngine
        engine = TqEngine(mode="kq")
        assert engine.mode == "kq"
        engine.close()

    def test_live_mode(self):
        """Live mode should succeed initialization."""
        from app.services.tq_engine import TqEngine
        engine = TqEngine(mode="live")
        assert engine.mode == "live"
        engine.close()

    def test_mode_case_insensitive(self):
        """Mode should be case-insensitive."""
        from app.services.tq_engine import TqEngine
        engine = TqEngine(mode="BACKTEST",
                          start_dt=datetime(2024, 1, 1),
                          end_dt=datetime(2024, 1, 31))
        assert engine.mode == "backtest"
        engine.close()
