"""Application layer: ports (interfaces) and use cases.

Per AGENTS.md invariant #9: this layer imports from domain (value
objects, entities) and defines ports (Protocol classes). It must
NOT import any concrete adapter (ccxt, ta, redis, structlog is OK
for use cases that log; ccxt/ta/redis are infrastructure).
"""
