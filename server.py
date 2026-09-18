"""Agent 1 exposed as a FastAPI microservice.

Run:
    uvicorn server:app --host 0.0.0.0 --port 8001

Endpoints:
    POST /api/v1/analyze      JSON body = Agent1_input.json -> Agent1_output.json
                             (or {"filename": "data/Agent1_input.json"} to load a saved input)
    GET  /api/v1/feed         merged news feed (junk headlines + supply-chain events)
    GET  /                    the news dashboard (static/index.html)
    GET  /health              service health
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models.input_schema import Agent1Input
from services.output_generator import generate

app = FastAPI(
    title="Agent 1 - Predictive Event Ingestion",
    version="1.0",
    description="Risk detection agent: external event -> risk assessment -> Agent2 payload",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
SUPPLY_PREFIX = "Agent1_input"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "Agent 1 - Predictive Event Ingestion", "version": "1.0"}


def _load_input(path: Path) -> Agent1Input:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return Agent1Input.model_validate(raw)


def _analyze(event: Agent1Input, inventory_score: Optional[int], skip_llm: bool) -> dict:
    if skip_llm:
        import config

        config.LLM_ENABLED = False
    result = generate(event, inventory_override=inventory_score)
    return result.to_dict()


@app.get("/api/v1/feed")
def feed() -> list:
    items: list[dict] = []

    # Junk headlines
    junk_path = DATA_DIR / "junk_news.json"
    if junk_path.exists():
        with open(junk_path, "r", encoding="utf-8") as fh:
            for j in json.load(fh):
                items.append({
                    "type": "junk",
                    "id": j.get("id"),
                    "headline": j.get("headline"),
                    "category": j.get("category"),
                    "source": j.get("source"),
                    "time": j.get("time"),
                })

    # Supply-chain events (input files)
    supply: list[dict] = []
    for p in sorted(DATA_DIR.glob(f"{SUPPLY_PREFIX}*.json")):
        try:
            ev = _load_input(p)
        except Exception:
            continue
        supply.append({
            "type": "analysis",
            "id": ev.event_id,
            "headline": f"{ev.event_name}: {ev.event_type} in {ev.country}",
            "category": ev.event_type,
            "source": ev.source or "Agency",
            "time": ev.event_timestamp.strftime("%b %d, %Y"),
            "filename": str(p.relative_to(BASE_DIR)),
            "severity": ev.severity,
            "event_name": ev.event_name,
        })

    # Interleave: junk, analysis, junk, junk, analysis, ...
    merged: list[dict] = []
    s_idx = 0
    junk_between = 2
    for i, item in enumerate(items):
        merged.append(item)
        if i % junk_between == 1 and s_idx < len(supply):
            merged.append(supply[s_idx])
            s_idx += 1
    while s_idx < len(supply):
        merged.append(supply[s_idx])
        s_idx += 1
    return merged


@app.post("/api/v1/analyze")
def analyze(
    payload: dict,
    inventory_score: Optional[int] = None,
    skip_llm: bool = False,
) -> dict:
    try:
        # Support {"filename": "data/Agent1_input.json"} for dashboard integration
        if "filename" in payload and not any(k in payload for k in Agent1Input.model_fields):
            path = (BASE_DIR / payload["filename"]).resolve()
            if not path.is_file():
                raise HTTPException(status_code=404, detail=f"Input file not found: {payload['filename']}")
            event = _load_input(path)
        else:
            event = Agent1Input.model_validate(payload)
        return _analyze(event, inventory_score, skip_llm)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Analysis failed: {exc}") from exc
