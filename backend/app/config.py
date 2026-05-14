import os
class Settings:
    """Settings read from environment at instantiation time (not import time)."""

    def __init__(self):
        # TqSdk
        self.tq_username: str = os.getenv("TQ_USERNAME", "")
        self.tq_password: str = os.getenv("TQ_PASSWORD", "")
        self.tq_broker: str = os.getenv("TQ_BROKER", "")
        self.tq_account_id: str = os.getenv("TQ_ACCOUNT_ID", "")
        self.tq_trade_pwd: str = os.getenv("TQ_TRADE_PWD", "")
        self.tq_mode: str = os.getenv("TQ_MODE", "backtest")

        # PostgreSQL
        self.pg_user: str = os.getenv("POSTGRES_USER", "quant")
        self.pg_password: str = os.getenv("POSTGRES_PASSWORD", "quant_pass")
        self.pg_db: str = os.getenv("POSTGRES_DB", "quantdb")
        self.pg_host: str = os.getenv("POSTGRES_HOST", "localhost")
        self.pg_port: int = int(os.getenv("POSTGRES_PORT", "5432"))

        # InfluxDB
        self.influxdb_url: str = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.influxdb_token: str = os.getenv("INFLUXDB_TOKEN", "quant_token")
        self.influxdb_org: str = os.getenv("INFLUXDB_ORG", "quant")
        self.influxdb_bucket: str = os.getenv("INFLUXDB_BUCKET", "market_data")

        # Redis / Celery
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        self.celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        # Rollover config
        self.rollover_strategy: str = os.getenv("ROLLOVER_STRATEGY", "independent")

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"


def get_settings() -> Settings:
    return Settings()
