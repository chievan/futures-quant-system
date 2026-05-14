import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import positions, data, strategies, research, market

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    try:
        await init_db()
        logger.info("Database ready.")
    except Exception as e:
        logger.warning(f"Database initialization skipped (not critical at startup): {e}")
    yield


app = FastAPI(
    title="Futures Quant Trading System",
    description="API for futures quantitative trading with TqSdk",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(positions.router)
app.include_router(data.router)
app.include_router(strategies.router)
app.include_router(research.router)
app.include_router(market.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
