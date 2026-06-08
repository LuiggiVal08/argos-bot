"""Incident API: declare and list incidents.

GET /incident/list — show recent incidents
POST /incident/declare — manually declare an incident
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..application.use_cases.list_incidents import ListIncidentsUseCase
from ..application.use_cases.report_incident import ReportIncidentUseCase
from ..composition import get_list_incidents_usecase, get_report_incident_usecase
from ..domain.value_objects.incident import IncidentSeverity


router = APIRouter(prefix="/incident", tags=["incident"])


class IncidentEventOut(BaseModel):
    incident_id: str
    severity: str
    source: str
    message: str
    phase: str
    timestamp: str
    metadata: dict[str, str]


class DeclareIncidentBody(BaseModel):
    severity: IncidentSeverity = Field(...)
    source: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=512)
    metadata: dict[str, str] = Field(default_factory=dict)


@router.get(
    "/list",
    response_model=list[IncidentEventOut],
    summary="List recent incidents.",
)
async def list_incidents(
    use_case: ListIncidentsUseCase = Depends(get_list_incidents_usecase),
    limit: int = 50,
) -> list[IncidentEventOut]:
    events = await use_case.execute(limit=limit)
    return [
        IncidentEventOut(
            incident_id=e.incident_id,
            severity=e.severity.value,
            source=e.source,
            message=e.message,
            phase=e.phase.value,
            timestamp=e.timestamp.isoformat(),
            metadata=e.metadata,
        )
        for e in events
    ]


@router.post(
    "/declare",
    response_model=IncidentEventOut,
    summary="Declare an incident manually.",
)
async def declare_incident(
    body: DeclareIncidentBody,
    use_case: ReportIncidentUseCase = Depends(get_report_incident_usecase),
) -> IncidentEventOut:
    event = await use_case.execute(
        severity=body.severity,
        source=body.source,
        message=body.message,
        metadata=body.metadata,
    )
    return IncidentEventOut(
        incident_id=event.incident_id,
        severity=event.severity.value,
        source=event.source,
        message=event.message,
        phase=event.phase.value,
        timestamp=event.timestamp.isoformat(),
        metadata=event.metadata,
    )
