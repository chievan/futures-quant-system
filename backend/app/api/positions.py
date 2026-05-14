from __future__ import annotations
from fastapi import APIRouter, Query

from app.services.tq_engine import TqEngine
from app.services.position_recorder import PositionRecorder

router = APIRouter(prefix="/api/positions", tags=["positions"])
recorder = PositionRecorder()


@router.get("/current")
async def get_current_positions():
    """Get current real-time positions (only works in kq/live mode)."""
    try:
        engine = TqEngine()
        api = engine.api
        positions = api.get_position()
        result = []
        for pos in positions:
            result.append({
                "symbol": pos.get("symbol", ""),
                "direction": pos.get("direction", ""),
                "volume": pos.get("volume", 0),
                "avg_price": pos.get("avg_price", 0.0),
                "last_price": pos.get("last_price", 0.0),
                "float_pnl": pos.get("float_pnl", 0.0),
                "margin": pos.get("margin", 0.0),
            })
        return {"positions": result}
    except Exception as e:
        return {"positions": [], "error": str(e)}


@router.get("/history/{task_id}")
async def get_position_history(task_id: str, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """Get position change history for a backtest task."""
    return await recorder.get_history(task_id, page, size)


@router.get("/analysis/{task_id}")
async def get_position_analysis(task_id: str):
    """Get P&L analysis for a backtest task."""
    return await recorder.get_analysis(task_id)


@router.get("/export/{task_id}")
async def export_position_report(task_id: str):
    """Export position report as CSV."""
    csv = await recorder.export_csv(task_id)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=positions_{task_id}.csv"},
    )
