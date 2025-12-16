The Resilient Store-and-Forward Telemetry System
================================================

Purpose-built to keep telemetry flowing in adversarial or flaky network environments. An edge Agent continuously collects data, safely buffers to disk if links drop, and drains the backlog to the Headquarters (HQ) service once connectivity returns.

Key Features
------------
- Fault tolerance via disk-backed buffer (`buffer.jsonl`) with atomic rotation before upload.
- Concurrency-safe Agent pipeline (Go routines + mutex-protected file access).
- Async ingestion stack (FastAPI + aiosqlite) to avoid blocking during spikes.
- Built-in chaos simulation that randomly severs the “network” to prove resilience end-to-end.

Architecture Diagram
--------------------
```mermaid
flowchart LR
    subgraph Edge Agent (Go)
        T[Telemetry Generator<br/>1 Hz JSON]
        B[Buffer Writer<br/>fileMutex-protected<br/>buffer.jsonl]
        F[Flush Worker<br/>rotate -> upload backlog]
    end

    subgraph Network / Chaos
        C[Chaos Flag<br/>is_network_healthy?]
    end

    subgraph Headquarters (FastAPI)
        A[POST /telemetry<br/>async validation]
        S[Async SQLite<br/>aiosqlite]
        D[Dashboard (HTMX)]
    end

    T -->|POST| A
    A --> S
    B -->|on failure| B
    B -->|on recovery| F --> A
    C -.toggles 503 .-> A
    S --> D
```

Chaos Mode (How to See the Breaks)
----------------------------------
- HQ runs a background asyncio task that randomly flips a global `is_network_healthy` flag.
- When the flag is `False`, `/telemetry` returns HTTP 503 to simulate a dropped link.
- The Agent treats 503 as a failure: it appends telemetry to `buffer.jsonl` and keeps producing data.
- As soon as the chaos flag turns healthy again, the Agent rotates `buffer.jsonl` to `buffer_processing.jsonl` and drains the backlog, then deletes the processed file.
- Verification: start both services, load the HQ dashboard at `http://localhost:8000/`. You’ll see the ingest graph stall during chaos windows and then catch up when connectivity returns.

Quick Start
-----------
- Prerequisites: Go 1.23+, Python 3.12+, `uv`.

HQ (Python/FastAPI)
```bash
cd hq
uv run uvicorn main:app --reload --port 8000
```
Open `http://localhost:8000/` for the dashboard.

Agent (Go)
```bash
cd agent
go run main.go
```
Watch logs for buffering (when chaos triggers) and backlog flushes (when connectivity returns).

Technical Deep Dive
-------------------
- Atomic file rotation (Agent): All buffer reads/writes are guarded by a global `fileMutex`. When connectivity is restored, the Agent renames `buffer.jsonl` to `buffer_processing.jsonl` atomically, uploads from the rotated file (never from the active writer), and deletes it only after successful transfer.
- Async SQLite (HQ): Incoming telemetry is validated via Pydantic models, then inserted with `aiosqlite` inside async routes. The shared connection is managed in FastAPI lifespan hooks so ingestion stays non-blocking during bursts and under chaos-induced retries.
