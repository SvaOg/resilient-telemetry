from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


# 1. Define the Data Schema
# This ensures we only accept valid data from the agent.
class TelemetryData(BaseModel):
    agent_id: str
    timestamp: datetime
    temperature: float
    battery_level: int


# 2. The ingestion Endpoint
@app.post("/telemetry")
async def receive_telemetry(data: TelemetryData):
    """Receives JSON data from the field agent."""
    # For now, we just print it to the console to prove it works.
    print(
        f"📡 [RECEIVED] Agent: {data.agent_id} | Temp: {data.temperature}°C | Battery: {data.battery_level}%"
    )

    return {"status": "received", "timestamp": datetime.now()}


# 3. Simple Health Check
@app.get("/")
async def root():
    return {"status": "HQ is online"}
