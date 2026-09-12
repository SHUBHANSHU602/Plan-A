from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.dependencies import get_exposure_service
from app.schemas.exposure import ExposureResponse
from app.services.exposure_service import ExposureService
from app.services.risk_service import RiskCellNotFoundError

router = APIRouter(prefix="/exposure", tags=["exposure"])


@router.get("/{cell_code}", response_model=ExposureResponse)
async def get_cell_exposure(
    cell_code: Annotated[str, Path(min_length=1, max_length=64)],
    service: Annotated[ExposureService, Depends(get_exposure_service)],
    radius_m: Annotated[float, Query(gt=0, le=50_000)] = 2_000,
) -> ExposureResponse:
    try:
        return await service.get_exposure(cell_code, radius_m)
    except RiskCellNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
