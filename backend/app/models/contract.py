from __future__ import annotations
import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContractMeta(Base):
    __tablename__ = "contract_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    granularity: Mapped[str] = mapped_column(String(8), nullable=False)  # tick / 1min / 5min / 15min / 30min / 60min / day
    start_date: Mapped[str] = mapped_column(String(16), nullable=False)
    end_date: Mapped[str] = mapped_column(String(16), nullable=False)
    total_bars: Mapped[int] = mapped_column(Integer, default=0)
    data_points: Mapped[int] = mapped_column(Integer, default=0)
    missing_ranges: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of missing intervals
    quality: Mapped[str] = mapped_column(String(8), default="green")  # green / yellow / red
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now)
