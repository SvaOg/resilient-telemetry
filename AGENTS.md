# AGENTS.md - Project Context & Guidelines

## 1. Project Overview
**Name:** Resilient Store-and-Forward Telemetry System
**Goal:** A distributed system demonstrating "Edge Computing" resilience. A Field Agent collects data and uploads it to a Headquarters. If the network is down, the Agent buffers data to disk and automatically syncs it when the connection is restored.

## 2. Architecture

### A. The "Edge" Agent (Go)
* **Location:** `/agent`
* **Role:** Simulates an IoT device (drone/sensor).
* **Behavior:**
    1.  Generates dummy telemetry (JSON) every 1s.
    2.  Attempts HTTP POST to HQ.
    3.  **Failure Mode:** If POST fails, appends JSON to local `buffer.jsonl`.
    4.  **Recovery Mode:** A background Goroutine checks for connectivity. If online, it rotates `buffer.jsonl` -> `buffer_processing.jsonl` and uploads the backlog.
* **Key Patterns:** `sync.Mutex` for file safety, Goroutines for background flushing, Atomic file rotation.

### B. The "Headquarters" (Python/FastAPI)
* **Location:** `/hq`
* **Role:** Central ingestion and visualization.
* **Behavior:**
    1.  Receives POST `/telemetry`.
    2.  Saves to SQLite (`telemetry.db`) asynchronously.
    3.  Serves an HTMX-powered dashboard at `/`.
    4.  **Chaos Simulation:** A background `asyncio` task randomly toggles a global `is_network_healthy` flag. If `False`, the API returns HTTP 503 to simulate network failure.
* **Key Patterns:** strictly `async/await`, `aiosqlite` for non-blocking DB, `lifespan` for connection management.

## 3. Tech Stack & Tooling

| Component | Technology | Management Tool |
| :--- | :--- | :--- |
| **Agent** | Go 1.23+ | `go mod` |
| **Backend** | Python 3.12+, FastAPI | `uv` |
| **Database** | SQLite + `aiosqlite` | (Built-in) |
| **Frontend** | HTML + HTMX + Jinja2 | (No build step) |

## 4. Development Commands

### Python HQ
cd hq
# Run server with auto-reload
uv run uvicorn main:app --reload --port 8000

###Go Agent
cd agent
# Run the agent
go run main.go


##5. Coding Guidelines (Strict)

###Python (HQ)1. 
1. **No Blocking I/O:** Never use standard `open()` or `sqlite3` inside async routes. Use `aiosqlite`.
2. **Concurrency:** Use `asyncio.create_task` for background workers (like Chaos Monkey).
3. **Type Safety:** Use Pydantic models for all API inputs/outputs.

###Go (Agent)
1. **Race Condition Safety:** ANY file access (read or write) must be protected by the global `fileMutex`.
2. **Error Handling:** Check all errors. If network fails, log and fallback to buffer.
3. **File Rotation:** Do not upload from the active write buffer. Rename (Rotate) -> Process -> Delete.

##6. Current State*
**Implemented:** Basic happy path, Store-and-Forward logic, Async Backend, Chaos Simulation, Dashboard.

* **Next Steps:**
* Add "Device Registration" handshake.
* Secure the endpoint (API Tokens).
* Add Unit Tests for the Go buffering logic.
