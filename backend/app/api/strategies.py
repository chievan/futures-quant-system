from __future__ import annotations
from typing import Optional
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete

from app.database import async_session_factory
from app.models.strategy import StrategyConfig

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config_json: str


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[str] = None


@router.get("/")
async def list_strategies():
    async with async_session_factory() as session:
        stmt = select(StrategyConfig).order_by(StrategyConfig.updated_at.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return {
            "strategies": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "config_json": r.config_json,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ]
        }


@router.post("/")
async def create_strategy(req: StrategyCreate):
    async with async_session_factory() as session:
        existing = await session.execute(
            select(StrategyConfig).where(StrategyConfig.name == req.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Strategy with this name already exists")

        sc = StrategyConfig(
            name=req.name,
            description=req.description,
            config_json=req.config_json,
        )
        session.add(sc)
        await session.commit()
        return {"id": sc.id, "name": sc.name}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: int):
    async with async_session_factory() as session:
        stmt = select(StrategyConfig).where(StrategyConfig.id == strategy_id)
        result = await session.execute(stmt)
        sc = result.scalar_one_or_none()
        if not sc:
            raise HTTPException(404, "Strategy not found")
        return {
            "id": sc.id,
            "name": sc.name,
            "description": sc.description,
            "config_json": sc.config_json,
            "created_at": sc.created_at.isoformat(),
            "updated_at": sc.updated_at.isoformat(),
        }


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: int, req: StrategyUpdate):
    async with async_session_factory() as session:
        stmt = select(StrategyConfig).where(StrategyConfig.id == strategy_id)
        result = await session.execute(stmt)
        sc = result.scalar_one_or_none()
        if not sc:
            raise HTTPException(404, "Strategy not found")
        if req.name is not None:
            sc.name = req.name
        if req.description is not None:
            sc.description = req.description
        if req.config_json is not None:
            sc.config_json = req.config_json
        sc.updated_at = datetime.now()
        await session.commit()
        return {"status": "updated"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: int):
    async with async_session_factory() as session:
        stmt = select(StrategyConfig).where(StrategyConfig.id == strategy_id)
        result = await session.execute(stmt)
        sc = result.scalar_one_or_none()
        if not sc:
            raise HTTPException(404, "Strategy not found")
        await session.delete(sc)
        await session.commit()
        return {"status": "deleted"}
