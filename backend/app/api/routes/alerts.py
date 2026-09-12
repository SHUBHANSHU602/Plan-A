from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies import get_alert_management_service
from app.schemas.alert import (
    AlertDetail,
    AlertListResponse,
    AlertSeverity,
    AlertStatus,
    AlertTransitionRequest,
    AlertTransitionResponse,
)
from app.services.alert_management_service import (
    AlertManagementService,
    AlertNotFoundError,
    InvalidAlertCursorError,
    InvalidAlertTransitionError,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    service: Annotated[AlertManagementService, Depends(get_alert_management_service)],
    alert_status: Annotated[AlertStatus | None, Query(alias="status")] = None,
    severity: AlertSeverity | None = None,
    cell_code: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertListResponse:
    try:
        return await service.list_alerts(
            status=alert_status,
            severity=severity,
            cell_code=cell_code,
            cursor=cursor,
            limit=limit,
        )
    except InvalidAlertCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert(
    alert_id: Annotated[UUID, Path()],
    service: Annotated[AlertManagementService, Depends(get_alert_management_service)],
) -> AlertDetail:
    try:
        return await service.get_alert(alert_id)
    except AlertNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{alert_id}/acknowledge", response_model=AlertTransitionResponse)
async def acknowledge_alert(
    alert_id: Annotated[UUID, Path()],
    request: AlertTransitionRequest,
    service: Annotated[AlertManagementService, Depends(get_alert_management_service)],
) -> AlertTransitionResponse:
    return await _transition(service, alert_id, AlertStatus.ACKNOWLEDGED, request)


@router.post("/{alert_id}/verify", response_model=AlertTransitionResponse)
async def verify_alert(
    alert_id: Annotated[UUID, Path()],
    request: AlertTransitionRequest,
    service: Annotated[AlertManagementService, Depends(get_alert_management_service)],
) -> AlertTransitionResponse:
    return await _transition(service, alert_id, AlertStatus.VERIFIED, request)


@router.post("/{alert_id}/resolve", response_model=AlertTransitionResponse)
async def resolve_alert(
    alert_id: Annotated[UUID, Path()],
    request: AlertTransitionRequest,
    service: Annotated[AlertManagementService, Depends(get_alert_management_service)],
) -> AlertTransitionResponse:
    return await _transition(service, alert_id, AlertStatus.RESOLVED, request)


async def _transition(
    service: AlertManagementService,
    alert_id: UUID,
    target: AlertStatus,
    request: AlertTransitionRequest,
) -> AlertTransitionResponse:
    try:
        return await service.transition(alert_id, target, request)
    except AlertNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidAlertTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
