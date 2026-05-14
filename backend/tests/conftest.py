"""Pytest fixtures for unit tests."""
import os
import pytest


@pytest.fixture(autouse=True)
def set_test_env():
    """Set test environment variables before each test."""
    os.environ.setdefault("TQ_USERNAME", "test_user")
    os.environ.setdefault("TQ_PASSWORD", "test_pass")
    os.environ.setdefault("TQ_BROKER", "test_broker")
    os.environ.setdefault("TQ_ACCOUNT_ID", "123456")
    os.environ.setdefault("TQ_TRADE_PWD", "test_trade_pwd")
    os.environ.setdefault("TQ_MODE", "backtest")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("INFLUXDB_URL", "http://localhost:8086")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


@pytest.fixture
def clean_env():
    """Remove TQ_MODE to test default."""
    old = os.environ.pop("TQ_MODE", None)
    yield
    if old:
        os.environ["TQ_MODE"] = old
