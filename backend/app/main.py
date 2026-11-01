import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api import api_router
from app.services.pipeline_runner import run_pipeline_loop, notify_pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline_task = None
    stop_event = asyncio.Event()
    if settings.EMBEDDED_PIPELINE and settings.APP_ENV != "test":
        pipeline_task = asyncio.create_task(run_pipeline_loop(stop_event=stop_event))
    try:
        yield
    finally:
        if pipeline_task:
            stop_event.set()
            notify_pipeline()
            try:
                await asyncio.wait_for(pipeline_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pipeline_task.cancel()

app = FastAPI(
    title="SETU",
    description="Adaptive Learning Desk for Classes 6-10",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "product": "SETU",
        "tagline": "The Learning Desk",
        "docsUrl": "/docs",
        "healthUrl": f"{settings.API_V1_PREFIX}/health"
    }

