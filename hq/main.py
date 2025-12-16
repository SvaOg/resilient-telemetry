import asyncio
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("HQ")

# --- CONFIGURATION ---
DB_FILE = "telemetry.db"
CHAOS_MODE = True  # Set to False to disable the simulation
MIN_UP_TIME = 5
MAX_UP_TIME = 10
MIN_DOWN_TIME = 3
MAX_DOWN_TIME = 7

templates = Jinja2Templates(directory="templates")

# --- GLOBAL STATE ---
db_connection = None
is_network_healthy = True  # Default to online


# --- CHAOS SIMULATION TASK ---
async def chaos_monkey_loop():
    """
    Background task that randomly toggles the server health status.
    """
    global is_network_healthy
    logger.info("🐵 Chaos Monkey started internally.")

    while True:
        # 1. Stay ONLINE for a random duration
        duration = random.randint(MIN_UP_TIME, MAX_UP_TIME)
        is_network_healthy = True
        logger.info(f"✅ Network RESTORED. Online for {duration}s")
        await asyncio.sleep(duration)

        # 2. Go OFFLINE for a random duration
        duration = random.randint(MIN_DOWN_TIME, MAX_DOWN_TIME)
        is_network_healthy = False
        logger.warning(f"💥 Network SEVERED. Offline for {duration}s")
        await asyncio.sleep(duration)


# --- DATABASE LOGIC ---
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
    # STARTUP
    global db_connection
    logger.info("Initializing Database...")
    db_connection = await aiosqlite.connect(DB_FILE)
    db_connection.row_factory = aiosqlite.Row
    await init_db(db_connection)

    # Start Chaos Monkey if enabled
    chaos_task = None
    if CHAOS_MODE:
        chaos_task = asyncio.create_task(chaos_monkey_loop())

    yield  # Application runs

    # SHUTDOWN
    if chaos_task:
        chaos_task.cancel()
    logger.info("Closing Database...")
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
    Ingest data. Fails with 503 if Chaos Monkey is active.
    """
    # 1. Chaos Check
    if not is_network_healthy:
        # Simulate a network failure (Service Unavailable)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simulated Network Failure",
        )

    # 2. Database Check
    if not db_connection:
        return {"status": "error", "message": "Database not ready"}

    # 3. Save Data (Async)
    async with db_connection.execute(
        """
        INSERT INTO readings (agent_id, timestamp, temperature, battery_level)
        VALUES (?, ?, ?, ?)
    """,
        (data.agent_id, data.timestamp, data.temperature, data.battery_level),
    ) as cursor:
        await db_connection.commit()

    logger.info(
        f"📥 Saved: {data.timestamp.strftime('%H:%M:%S')} | Temp: {data.temperature}"
    )
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

    async with db_connection.execute("SELECT COUNT(*) FROM readings") as cursor:
        row = await cursor.fetchone()
        count = row[0] if row else 0

    async with db_connection.execute(
        "SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1"
    ) as cursor:
        latest = await cursor.fetchone()

    # Pass the 'is_network_healthy' status to the template so we can visualize it!
    return templates.TemplateResponse(
        "stats_fragment.html",
        {
            "request": request,
            "count": count,
            "latest": latest,
            "online": is_network_healthy,  # New context variable
        },
    )
