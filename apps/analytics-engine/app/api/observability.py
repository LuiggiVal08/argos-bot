from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..application.use_cases.collect_telemetry import (
    CollectTelemetryUseCase,
    RecordTelemetryUseCase,
)
from ..application.use_cases.report_incident_extended import (
    GetDisasterStatusUseCase,
    RecoverFromIncidentUseCase,
    ReportIncidentExtendedUseCase,
)
from ..application.use_cases.update_dashboard import (
    GetDashboardUseCase,
    GetDashboardHistoryUseCase,
    UpdateDashboardUseCase,
)
from ..composition import (
    get_collect_telemetry_usecase,
    get_record_telemetry_usecase,
    get_disaster_status_usecase,
    get_report_incident_extended_usecase,
    get_recover_from_incident_usecase,
    get_dashboard_usecase,
    get_dashboard_history_usecase,
    get_update_dashboard_usecase,
)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/telemetry", summary="Get current telemetry snapshot")
async def get_telemetry(request: Request) -> dict:
    uc: CollectTelemetryUseCase = get_collect_telemetry_usecase(request)
    result = await uc.execute()
    return {
        "snapshot": {
            "data_engine": result.snapshot.data_engine,
            "analytics_engine": result.snapshot.analytics_engine,
            "execution_engine": result.snapshot.execution_engine,
            "training_engine": result.snapshot.training_engine,
            "timestamp": result.snapshot.timestamp,
        },
        "recent_metrics": result.recent_metrics,
    }


@router.post("/telemetry/record", summary="Record telemetry metrics")
async def record_telemetry(
    request: Request,
    data_engine: dict[str, float] | None = None,
    analytics_engine: dict[str, float] | None = None,
    execution_engine: dict[str, float] | None = None,
    training_engine: dict[str, float] | None = None,
) -> dict:
    uc: RecordTelemetryUseCase = get_record_telemetry_usecase(request)
    await uc.record_all(
        data_engine=data_engine,
        analytics_engine=analytics_engine,
        execution_engine=execution_engine,
        training_engine=training_engine,
    )
    return {"status": "ok"}


@router.get("/dashboard", summary="Get current dashboard state")
async def get_dashboard(request: Request) -> dict:
    uc: GetDashboardUseCase = get_dashboard_usecase(request)
    panel = await uc.execute()
    return {
        "market": panel.market,
        "ai": panel.ai,
        "risk": panel.risk,
        "training": panel.training,
        "updated_at": panel.updated_at,
    }


@router.get("/dashboard/history", summary="Get dashboard history")
async def get_dashboard_history(request: Request, limit: int = 100) -> list[dict]:
    uc: GetDashboardHistoryUseCase = get_dashboard_history_usecase(request)
    return await uc.execute(limit=limit)


@router.post("/dashboard/update", summary="Update dashboard panels")
async def update_dashboard(
    request: Request,
    market: dict[str, Any] | None = None,
    ai: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    training: dict[str, Any] | None = None,
) -> dict:
    uc: UpdateDashboardUseCase = get_update_dashboard_usecase(request)
    await uc.execute(market=market, ai=ai, risk=risk, training=training)
    return {"status": "ok"}


@router.get("/disaster/status", summary="Get disaster recovery status")
async def disaster_status(request: Request) -> dict:
    uc: GetDisasterStatusUseCase = get_disaster_status_usecase(request)
    status = await uc.execute()
    return {
        "mode": status.mode,
        "total_incidents": status.total_incidents,
        "consecutive_failures": status.consecutive_failures,
        "unrecovered": status.unrecovered,
    }


@router.post("/disaster/report", summary="Report an incident to disaster recovery")
async def report_incident(
    request: Request,
    event_type: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict:
    uc: ReportIncidentExtendedUseCase = get_report_incident_extended_usecase(request)
    event = await uc.execute(event_type, severity, message, details)
    return {
        "event_type": event.event_type,
        "severity": event.severity.value,
        "message": event.message,
        "timestamp": event.timestamp,
    }


@router.post("/disaster/recover", summary="Recover from an incident")
async def recover_from_incident(request: Request, event_type: str) -> dict:
    uc: RecoverFromIncidentUseCase = get_recover_from_incident_usecase(request)
    result = await uc.execute(event_type)
    return result
