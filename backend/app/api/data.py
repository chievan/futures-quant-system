from __future__ import annotations
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.data_service import DataService
from app.tasks.data_download import download_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data", tags=["data"])
service = DataService()


class DownloadRequest(BaseModel):
    symbol: str
    granularity: str
    start_date: str
    end_date: str


class DeleteRequest(BaseModel):
    symbol: str
    granularity: str
    start_date: str
    end_date: str


@router.get("/contracts")
async def get_contracts():
    """Summary of all persisted contracts."""
    return {"contracts": await service.get_contracts_summary()}


@router.get("/info/{contract}")
async def get_contract_info(contract: str):
    """Detailed coverage for a contract symbol."""
    return {"contracts": await service.get_contract_info(contract)}


@router.delete("/delete")
async def delete_data(req: DeleteRequest):
    """Delete data for a specific time range and granularity."""
    await service.delete_data(req.symbol, req.granularity, req.start_date, req.end_date)
    return {"status": "deleted"}


@router.post("/download")
async def create_download_task(req: DownloadRequest):
    """Create a new data download task."""
    task_id = str(uuid.uuid4())

    # Validate granularity
    from app.services.data_service import GRANULARITY_MAP
    if req.granularity not in GRANULARITY_MAP:
        raise HTTPException(400, f"Unsupported granularity: {req.granularity}")

    # Create DB record
    from app.database import async_session_factory
    from app.models.download_task import DownloadTask
    async with async_session_factory() as session:
        dt = DownloadTask(
            task_id=task_id,
            symbol=req.symbol,
            granularity=req.granularity,
            start_date=req.start_date,
            end_date=req.end_date,
            status="pending",
        )
        session.add(dt)
        await session.commit()

    # Dispatch Celery task
    download_data.delay(req.symbol, req.granularity, req.start_date, req.end_date, task_id)

    return {"task_id": task_id, "status": "pending"}


@router.get("/tasks")
async def get_download_tasks():
    """List all download tasks."""
    from app.database import async_session_factory
    from app.models.download_task import DownloadTask
    from sqlalchemy import select

    async with async_session_factory() as session:
        stmt = select(DownloadTask).order_by(DownloadTask.created_at.desc())
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "symbol": t.symbol,
                    "granularity": t.granularity,
                    "start_date": t.start_date,
                    "end_date": t.end_date,
                    "status": t.status,
                    "progress": t.progress,
                    "total_bars": t.total_bars,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks
            ]
        }


@router.get("/quality/{contract}")
async def get_data_quality(contract: str):
    """Check data quality / detect missing ranges."""
    issues = await service.check_quality(contract)
    return {"contract": contract, "issues": issues}


@router.post("/quality/recheck")
async def recheck_all_quality():
    """Re-check quality for all contracts."""
    results = await service.run_full_quality_check()
    return {"results": results}
