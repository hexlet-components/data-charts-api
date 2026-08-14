import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg
from dotenv import load_dotenv
import json

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# Сколько строк курсор забирает из базы за один заход. По умолчанию asyncpg
# берёт 50, и месячная выборка в 46 тысяч строк превращается в 900 с лишним
# обращений к базе вместо полусотни: время ответа определяется задержкой сети,
# а не объёмом данных.
CURSOR_PREFETCH = 1000

# Записи склеиваются перед отправкой. Иначе каждая строка уходит клиенту
# отдельным чанком, и на годовой выборке это четверть миллиона чанков.
CHUNK_SIZE = 1000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Define it in the environment or .env file."
        )
    try:
        app.state.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logging.info("Connected to database successfully")
    except Exception as e:
        logging.error(f"Failed to connect to the database: {str(e)}")
        raise RuntimeError(
            "Failed to connect to the database. "
            "Check DATABASE_URL and DB availability."
        ) from e
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
async def health(db=Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Database unavailable")


def encode_datetime(value):
    # Единственный тип в обеих таблицах, который json не сериализует сам.
    # Формат тот же, что давал jsonable_encoder, но втрое дешевле: тот
    # рекурсивно обходит значение и разбирает его тип на каждой записи.
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


async def stream_records(db, query: str, begin: datetime, end: datetime):
    async def generator():
        # Скобки закрываются ровно один раз, в нормальном потоке. Прежний
        # вариант закрывал массив в finally, и на пустом диапазоне к уже
        # отданному "[]" добавлялась вторая скобка: ответ "[]]" не разбирался
        # как JSON вообще.
        try:
            yield "["
            first = True
            chunk = []
            async with db.transaction():
                cursor = db.cursor(query, begin, end, prefetch=CURSOR_PREFETCH)
                async for record in cursor:
                    chunk.append(json.dumps(
                        dict(record),
                        separators=(",", ":"),
                        default=encode_datetime,
                    ))
                    if len(chunk) >= CHUNK_SIZE:
                        yield ("" if first else ",") + ",".join(chunk)
                        first = False
                        chunk.clear()
            if chunk:
                yield ("" if first else ",") + ",".join(chunk)
            yield "]"
        except Exception as e:
            # Массив намеренно остаётся незакрытым: оборванный поток должен
            # быть виден клиенту как битый JSON. Валидный короткий массив
            # неотличим от полного ответа, и часть данных теряется молча.
            logging.error(f"Error streaming records: {str(e)}")
            raise

    return StreamingResponse(generator(), media_type="application/json")


@app.get("/visits")
async def get_visits(
    begin: str = Query(..., description="Start date in ISO format"),
    end: str = Query(..., description="End date in ISO format"),
    db=Depends(get_db)
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
    db=Depends(get_db)
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
