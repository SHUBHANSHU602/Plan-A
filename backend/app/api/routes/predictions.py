from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_risk_service
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.risk_service import (
    IncompleteCellFeaturesError,
    RiskCellNotFoundError,
    RiskService,
)

router = APIRouter(prefix="/predict", tags=["risk"])


@router.post("", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED)
async def predict_risk(
    request: PredictionRequest,
    service: Annotated[RiskService, Depends(get_risk_service)],
) -> PredictionResponse:
    try:
        return await service.predict(request)
    except RiskCellNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except IncompleteCellFeaturesError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
