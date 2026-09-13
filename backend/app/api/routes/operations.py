from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_rainfall_ingestion_service, get_simulation_service
from app.schemas.operations import (
    RainfallObservationCreate,
    RainfallObservationResponse,
    RainfallSimulationRequest,
    RainfallSimulationResponse,
)
from app.services.rainfall_ingestion_service import (
    RainfallIngestionService,
    RainfallObservationConflictError,
)
from app.services.risk_service import RiskCellNotFoundError
from app.services.simulation_service import (
    SimulatedRainfallLimitError,
    SimulationBaselineNotFoundError,
    SimulationService,
)

router = APIRouter(tags=["operations"])


@router.post(
    "/rainfall/observations",
    response_model=RainfallObservationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_rainfall_observation(
    request: RainfallObservationCreate,
    service: Annotated[RainfallIngestionService, Depends(get_rainfall_ingestion_service)],
) -> RainfallObservationResponse:
    try:
        return await service.enqueue(request)
    except RiskCellNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RainfallObservationConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/simulation/rainfall",
    response_model=RainfallSimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_rainfall(
    request: RainfallSimulationRequest,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> RainfallSimulationResponse:
    try:
        return await service.simulate(request)
    except RiskCellNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SimulationBaselineNotFoundError as error:
        raise HTTPException(
            status_code=409,
            detail="no baseline rainfall is available; provide baseline_rainfall_mm",
        ) from error
    except SimulatedRainfallLimitError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
