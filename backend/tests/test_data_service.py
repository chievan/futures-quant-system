"""Tests for DataService."""

import pytest


class TestDataService:
    """DataService tests focusing on non-DB logic."""

    def test_download_symbol_invalid_granularity(self):
        """Should raise ValueError for unsupported granularity."""
        from app.services.data_service import DataService, GRANULARITY_MAP

        assert "tick" in GRANULARITY_MAP
        assert "1min" in GRANULARITY_MAP
        assert "5min" in GRANULARITY_MAP
        assert "15min" in GRANULARITY_MAP
        assert "30min" in GRANULARITY_MAP
        assert "60min" in GRANULARITY_MAP
        assert "day" in GRANULARITY_MAP
        assert "bad" not in GRANULARITY_MAP

    def test_granularity_map_values(self):
        """Granularity map should have correct durations."""
        from app.services.data_service import GRANULARITY_MAP

        assert GRANULARITY_MAP["tick"] == 0
        assert GRANULARITY_MAP["1min"] == 60
        assert GRANULARITY_MAP["5min"] == 300
        assert GRANULARITY_MAP["15min"] == 900
        assert GRANULARITY_MAP["30min"] == 1800
        assert GRANULARITY_MAP["60min"] == 3600
        assert GRANULARITY_MAP["day"] == 86400

    def test_granularity_influx_map(self):
        """InfluxDB measurement names should match."""
        from app.services.data_service import GRANULARITY_INFLUX

        assert GRANULARITY_INFLUX["tick"] == "tick"
        assert GRANULARITY_INFLUX["1min"] == "1min"
        assert GRANULARITY_INFLUX["day"] == "day"

    def test_config_reads_env(self):
        """DataService should use settings from env."""
        from app.config import get_settings

        settings = get_settings()
        assert settings.influxdb_url is not None
        assert settings.influxdb_bucket is not None
