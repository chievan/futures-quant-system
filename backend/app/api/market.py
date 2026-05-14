from __future__ import annotations
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.tq_engine import TqEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["market"])


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.active:
            self.active[symbol] = []
        self.active[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.active:
            self.active[symbol] = [ws for ws in self.active[symbol] if ws != websocket]
            if not self.active[symbol]:
                del self.active[symbol]

    async def broadcast(self, symbol: str, data: dict):
        if symbol in self.active:
            for ws in self.active[symbol]:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/market/{symbol}")
async def market_data_websocket(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time market data."""
    await manager.connect(websocket, symbol)
    engine = TqEngine()

    try:
        # Subscribe to quote
        quote = engine.subscribe_quote(symbol)
        kline = engine.subscribe_kline(symbol, 60)

        loop = asyncio.get_event_loop()

        while True:
            await loop.run_in_executor(None, engine.api.wait_update)

            if engine.api.is_changing(quote):
                data = {
                    "symbol": symbol,
                    "last_price": float(quote.last_price),
                    "bid_price1": float(quote.bid_price1),
                    "ask_price1": float(quote.ask_price1),
                    "volume": int(quote.volume),
                    "open_interest": int(quote.open_interest),
                    "timestamp": quote.datetime,
                }
                await manager.broadcast(symbol, data)

            if engine.api.is_changing(kline.iloc[-1]):
                bar = kline.iloc[-1]
                kline_data = {
                    "type": "kline",
                    "symbol": symbol,
                    "datetime": bar["datetime"],
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": int(bar["volume"]),
                }
                await manager.broadcast(symbol, kline_data)

            # Small sleep to prevent tight loop
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        manager.disconnect(websocket, symbol)
    except Exception as e:
        logger.exception(f"WebSocket error for {symbol}")
        manager.disconnect(websocket, symbol)
    finally:
        engine.close()
