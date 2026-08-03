from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import data_status, meta, locate, search, schools, datacenter, match, plan, auth, major_catalog, hot_schools
from app.config import CORS_ORIGINS
from app import db, user_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    user_db.init_db()
    yield
    db.close_pool()


app = FastAPI(title="辽宁志愿参谋 API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(data_status.router, prefix=API_PREFIX)
app.include_router(meta.router, prefix=API_PREFIX)
app.include_router(locate.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(schools.router, prefix=API_PREFIX)
app.include_router(datacenter.router, prefix=API_PREFIX)
app.include_router(match.router, prefix=API_PREFIX)
app.include_router(plan.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(major_catalog.router, prefix=API_PREFIX)
app.include_router(hot_schools.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
