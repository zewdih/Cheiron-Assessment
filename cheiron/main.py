import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cheiron.api.routes import router
from cheiron.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info("Cheiron starting up")
    yield
    logging.getLogger(__name__).info("Cheiron shutting down")


app = FastAPI(
    title="Cheiron — Clinical Trials Visualization Agent",
    description=(
        "AI-enabled backend that converts natural-language questions about "
        "clinical trials into structured visualization specifications, "
        "backed by the ClinicalTrials.gov API."
    ),
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

app.include_router(router, prefix="/api/v1", tags=["query"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "cheiron"}
