from __future__ import annotations
import os
from datetime import datetime
from typing import Optional

from tqsdk import TqApi, TqAccount, TqKq, TqSim, TqAuth, TqBacktest

from app.config import get_settings

settings = get_settings()


class TqEngine:
    """Unified TqApi interface supporting backtest / kq simulation / live trading modes."""

    def __init__(self, mode: Optional[str] = None,
                 start_dt: Optional[datetime] = None,
                 end_dt: Optional[datetime] = None):
        self.mode = (mode or settings.tq_mode).lower()
        self._api: Optional[TqApi] = None
        self._start_dt = start_dt
        self._end_dt = end_dt

    def _build_api(self) -> TqApi:
        auth = TqAuth(settings.tq_username, settings.tq_password)

        if self.mode == "live":
            api = TqApi(
                TqAccount(settings.tq_broker, settings.tq_account_id, settings.tq_trade_pwd),
                auth=auth,
            )
        elif self.mode == "kq":
            api = TqApi(TqKq(), auth=auth)
        else:
            if self._start_dt is None or self._end_dt is None:
                raise ValueError("start_dt and end_dt are required for backtest mode")
            api = TqApi(
                TqSim(),
                backtest=TqBacktest(self._start_dt, self._end_dt),
                auth=auth,
            )
        return api

    @property
    def api(self) -> TqApi:
        if self._api is None:
            self._api = self._build_api()
        return self._api

    def close(self):
        if self._api is not None:
            self._api.close()
            self._api = None

    def get_position(self):
        """Fetch all current positions from TqApi."""
        return self.api.get_position()

    def subscribe_quote(self, symbol: str):
        """Subscribe to real-time quote for a symbol."""
        return self.api.get_quote(symbol)

    def subscribe_kline(self, symbol: str, duration_seconds: int = 60):
        """Subscribe to kline data."""
        return self.api.get_kline_serial(symbol, duration_seconds)

    def subscribe_tick(self, symbol: str):
        """Subscribe to tick data."""
        return self.api.get_tick_serial(symbol)
