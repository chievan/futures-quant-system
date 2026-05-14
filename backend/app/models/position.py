from __future__ import annotations
import datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PositionChange(Base):
    __tablename__ = "position_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # long / short
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    is_rollover: Mapped[bool] = mapped_column(Boolean, default=False)
    old_symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
