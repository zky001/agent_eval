from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.datasets import router as datasets_router
from app.api.leaderboard import router as leaderboard_router
from app.api.models import router as models_router
from app.api.runs import router as runs_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Agent Evaluation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(leaderboard_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Agent Evaluation Platform API"}
