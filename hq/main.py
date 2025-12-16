import logging
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HQ")

# --- CONFIGURATION ---
DB_FILE = "telemetry.db"
templates = Jinja2Templates(directory="templates")

# --- DATABASE CONNECTION MANAGEMENT ---
# We use a global state (or dependency injection) for the DB connection.
# For this scale, a global managed by lifespan is clean and effective.
db_connection = None


async def init_db(conn: aiosqlite.Connection):
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            timestamp DATETIME,
            temperature REAL,
            battery_level INTEGER,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    await conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Connect to DB
    global db_connection
    logger.info("Initializing Database Connection...")
    db_connection = await aiosqlite.connect(DB_FILE)
    # Enable row access by name
    db_connection.row_factory = aiosqlite.Row

    await init_db(db_connection)

    yield  # Application runs here

    # SHUTDOWN: Close DB
    logger.info("Closing Database Connection...")
    await db_connection.close()


app = FastAPI(lifespan=lifespan)


# --- DATA MODELS ---
class TelemetryData(BaseModel):
    agent_id: str
    timestamp: datetime
    temperature: float
    battery_level: int


# --- API ENDPOINTS ---


@app.post("/telemetry")
async def receive_telemetry(data: TelemetryData):
    """
    Ingest data asynchronously.
    """
    if not db_connection:
        return {"status": "error", "message": "Database not ready"}

    async with db_connection.execute(
        """
        INSERT INTO readings (agent_id, timestamp, temperature, battery_level)
        VALUES (?, ?, ?, ?)
    """,
        (data.agent_id, data.timestamp, data.temperature, data.battery_level),
    ) as cursor:
        await db_connection.commit()

    logger.info(f"✅ Saved: {data.timestamp} | Temp: {data.temperature}")
    return {"status": "saved"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
async def get_stats(request: Request):
    """
    Returns a partial HTML snippet with the latest stats.
    Non-blocking DB queries.
    """
    if not db_connection:
        return "Database Error"

    # Async query for count
    async with db_connection.execute("SELECT COUNT(*) FROM readings") as cursor:
        row = await cursor.fetchone()
        count = row[0] if row else 0

    # Async query for latest reading
    async with db_connection.execute(
        "SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1"
    ) as cursor:
        latest = await cursor.fetchone()

    return templates.TemplateResponse(
        "stats_fragment.html", {"request": request, "count": count, "latest": latest}
    )


if __name__ == "__main__":
    uvicorn.run(app, port=8000)
