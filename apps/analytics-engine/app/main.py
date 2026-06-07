"""Argos analytics & IA engine entry point."""
import os
import structlog
from fastapi import FastAPI

log = structlog.get_logger()
app = FastAPI(title="argos-analytics-engine", version="0.0.1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": os.environ.get("ENVIRONMENT_MODE", "PAPER_TRADING")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
