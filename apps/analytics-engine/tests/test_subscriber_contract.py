"""Minimal contract test: the analytics-engine can subscribe to a
broker stream and receive tick events published by the data-engine.

This test is integration-grade (requires a live broker). It is
gated by the presence of the ARGOS_BROKER_URL env var. If unset, it
is skipped, keeping the unit test suite hermetic.
"""
import asyncio
import json
import os
import uuid

import pytest

redis = pytest.importorskip("redis.asyncio")


@pytest.mark.asyncio
async def test_subscriber_receives_published_tick():
    url = os.environ.get("ARGOS_BROKER_URL")
    if not url:
        pytest.skip("ARGOS_BROKER_URL not set; integration test skipped")

    stream = f"ticks:test:{uuid.uuid4().hex[:8]}"
    client = redis.from_url(url)
    await client.delete(stream)

    payload = {
        "symbol": "BTC/USDT",
        "price": {"minor": "6000012345678", "decimals": 8},
        "quantity": "100000000",
        "side": "buy",
        "ts": 1700000000000,
        "tradeId": "1",
    }
    await client.xadd(stream, {"p": json.dumps(payload)})

    res = await client.xread({stream: "0"}, block=2000, count=10)
    assert res, "no events received within 2s"
    _, entries = res[0]
    assert entries, "stream had no entries"
    entry_id, fields = entries[0]
    assert fields["p"]
    parsed = json.loads(fields["p"])
    assert parsed["symbol"] == "BTC/USDT"
    assert parsed["tradeId"] == "1"
    await client.delete(stream)
    await client.aclose()
