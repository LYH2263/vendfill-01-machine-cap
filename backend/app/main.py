from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # 轻量迁移：旧库补出整机补货上限列（0 = 不限制，保持现网满补行为）。
    # 用 inspector 判存在，Postgres/SQLite 均可移植。
    insp = inspect(engine)
    if "locations" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("locations")}
        if "max_fill_qty" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE locations ADD COLUMN max_fill_qty INTEGER DEFAULT 0"))
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
