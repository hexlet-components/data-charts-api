import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg
from dotenv import load_dotenv
import json

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Define it in the environment or .env file.")
    try:
        app.state.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logging.info("Connected to database successfully")
    except Exception as e:
        logging.error(f"Failed to connect to the database: {str(e)}")
        raise RuntimeError("Failed to connect to the database. Check DATABASE_URL and DB availability.") from e
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

@app.get("/health")
async def health(db = Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Database unavailable")


async def stream_records(db, query: str, begin: datetime, end: datetime):
    async def generator():
        try:
            async with db.transaction():
                cursor = db.cursor(query, begin, end)
                iterator = cursor.__aiter__()
                try:
                    first_record = await iterator.__anext__()
                except StopAsyncIteration:
                    yield "[]"
                    return

                payload = json.dumps(
                    jsonable_encoder(dict(first_record)),
                    separators=(",", ":"),
                )
                yield "[" + payload

                async for record in iterator:
                    payload = json.dumps(
                        jsonable_encoder(dict(record)),
                        separators=(",", ":"),
                    )
                    yield "," + payload
        except Exception as e:
            logging.error(f"Error streaming records: {str(e)}")
            raise
        finally:
            yield "]"

    return StreamingResponse(generator(), media_type="application/json")


@app.get("/visits")
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
        return await stream_records(db, query, begin, end)
    except Exception as e:
        logging.error(f"Error fetching visits: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching visits"
        )

@app.get("/registrations")
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
        return await stream_records(db, query, begin, end)
    except Exception as e:
        logging.error(f"Error fetching registrations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching registrations"
        )
