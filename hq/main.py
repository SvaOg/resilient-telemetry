from datetime import datetime
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- DATABASE SETUP ---
DB_FILE = "telemetry.db"


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
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


init_db()


# --- DATA MODELS ---


# 1. Define the Data Schema
# This ensures we only accept valid data from the agent.
class TelemetryData(BaseModel):
    agent_id: str
    timestamp: datetime
    temperature: float
    battery_level: int


# --- API ENDPOINTS ---


# 2. The ingestion Endpoint
@app.post("/telemetry")
async def receive_telemetry(data: TelemetryData):
    """Ingest data and save to SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO readings (agent_id, timestamp, temperature, battery_level)
            VALUES (?, ?, ?, ?)
        """,
            (data.agent_id, data.timestamp, data.temperature, data.battery_level),
        )

    print(f"✅ Saved: {data.timestamp} | Temp: {data.temperature}")
    return {"status": "saved"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
async def get_stats(request: Request):
    """
    Returns a partial HTML snippet with the latest stats.
    HTMX will swap this into the page every 1 second.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        # Get total count
        count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        # Get latest reading
        latest = conn.execute(
            "SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

    return templates.TemplateResponse(
        "stats_fragment.html", {"request": request, "count": count, "latest": latest}
    )
