import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20
    )
    FastAPICache.init(InMemoryBackend())
    yield
    await app.state.pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)

async def get_db():
    async with app.state.pool.acquire() as conn:
        yield conn


@app.get("/")
async def index():
    return {"status": "It Works"}


@app.get("/visits")
@cache(expire=300)
async def get_visits(
    begin: str = Query(..., description="Start date in ISO format"),
    end: str = Query(..., description="End date in ISO format"),
    db = Depends(get_db)
):
    begin = datetime.fromisoformat(begin)
    end = datetime.fromisoformat(end)
    try:
        query = """
            SELECT *
            FROM visits
            WHERE visits.datetime BETWEEN $1 AND $2
        """
        records = await db.fetch(query, begin, end)
        return records
    except Exception as e:
        logging.error(f"Error fetching visits: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching visits"
        )

@app.get("/registrations")
@cache(expire=300)
async def get_registrations(
    begin: str = Query(..., description="Start date in ISO format"),
    end: str = Query(..., description="End date in ISO format"),
    db = Depends(get_db)
):
    begin = datetime.fromisoformat(begin)
    end = datetime.fromisoformat(end)
    try:
        query = """
            SELECT *
            FROM registrations
            WHERE registrations.datetime BETWEEN $1 AND $2
        """
        records = await db.fetch(query, begin, end)
        return records
    except Exception as e:
        logging.error(f"Error fetching registrations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching registrations"
        )
