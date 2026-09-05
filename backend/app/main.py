import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import auth
from app.api.v1.routers import analysis
from app.api.v1.routers import ownership
from app.api.v1.routers import research
from app.core.config import get_settings


logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research.router)
app.include_router(auth.router)
app.include_router(ownership.router)
app.include_router(analysis.router)


@app.on_event("startup")
def log_database_configuration() -> None:
    if get_settings().database_configured:
        logger.info("Database persistence is configured.")
    else:
        logger.warning(
            "Database persistence is disabled because DATABASE_URL is not configured."
        )


@app.get("/")
def root():
    return {"message": "ResearchPilot API is running"}
