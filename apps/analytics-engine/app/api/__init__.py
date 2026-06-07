"""API routes (HTTP entry points)."""
from .risk import router as risk_router

__all__ = ["risk_router"]
