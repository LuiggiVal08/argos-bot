"""Argos analytics & IA engine entry point."""
import asyncio
import os
import structlog
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI

log = structlog.get_logger()
app = FastAPI(title="argos-analytics-engine", version="0.0.1")


@asynccontextmanager
async def lifespan(_: FastAPI):
    consumer_task = asyncio.create_task(_consume_ticks())
    try:
        yield
    finally:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


app.router.lifespan_context = lifespan


async def _consume_ticks() -> None:
    """H1 subscriber: pull every tick from the broker stream and log it.

    Real analytics (DataFrame updates, indicators) is added in later
    stories. For H1 we just prove end-to-end flow works.
    """
    url = os.environ.get("ARGOS_BROKER_URL", "redis://localhost:6379")
    stream = f"ticks:{os.environ.get('SYMBOL', 'BTC/USDT').replace('/', '').lower()}"
    last_id = "$"
    client = redis.from_url(url)
    log.info("subscriber_started", url=url, stream=stream)
    try:
        while True:
            try:
                res = await client.xread({"stream": last_id}, block=1000, count=100)
            except Exception as e:
                log.warning("xread_error", error=str(e))
                await asyncio.sleep(1)
                continue
            if not res:
                continue
            for _stream, entries in res:
                for entry_id, fields in entries:
                    last_id = entry_id
                    payload = fields.get("p")
                    if not payload:
                        continue
                    try:
                        import json

                        tick = json.loads(payload)
                        log.info(
                            "tick_received",
                            symbol=tick.get("symbol"),
                            trade_id=tick.get("tradeId"),
                            price_minor=tick.get("price", {}).get("minor"),
                            ts=tick.get("ts"),
                        )
                    except Exception as e:
                        log.warning("tick_parse_error", error=str(e))
    except asyncio.CancelledError:
        log.info("subscriber_cancelled")
        await client.aclose()
        raise


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "mode": os.environ.get("ENVIRONMENT_MODE", "PAPER_TRADING"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
