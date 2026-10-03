from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_location_cap_column():
    """create_all does not alter existing tables; add max_fill_total if missing."""
    insp = inspect(engine)
    if "locations" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("locations")}
    if "max_fill_total" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE locations ADD COLUMN max_fill_total INTEGER NOT NULL DEFAULT 0"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_location_cap_column()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="VendFill", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
