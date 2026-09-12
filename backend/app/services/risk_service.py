from app.db.transaction import TransactionManager
from app.models.risk import RiskSnapshot
from app.repositories.risk import RiskCellRepository, RiskSnapshotRepository
from app.schemas.prediction import ModelFeatures, PredictionRequest, PredictionResponse
from app.services.alert_service import AlertService
from app.services.model_gateway import ModelGateway
from app.services.risk_classifier import RiskClassifier


class RiskCellNotFoundError(Exception):
    def __init__(self, cell_code: str) -> None:
        super().__init__(f"risk cell '{cell_code}' was not found")
        self.cell_code = cell_code


class IncompleteCellFeaturesError(Exception):
    def __init__(self, cell_code: str, missing_fields: list[str]) -> None:
        fields = ", ".join(missing_fields)
        super().__init__(f"risk cell '{cell_code}' is missing model features: {fields}")
        self.cell_code = cell_code
        self.missing_fields = missing_fields


class RiskService:
    def __init__(
        self,
        cell_repository: RiskCellRepository,
        snapshot_repository: RiskSnapshotRepository,
        model_gateway: ModelGateway,
        classifier: RiskClassifier,
        alert_service: AlertService,
        transaction: TransactionManager,
    ) -> None:
        self._cell_repository = cell_repository
        self._snapshot_repository = snapshot_repository
        self._model_gateway = model_gateway
        self._classifier = classifier
        self._alert_service = alert_service
        self._transaction = transaction

    async def predict(self, request: PredictionRequest) -> PredictionResponse:
        feature_set = await self._cell_repository.get_feature_set(request.cell_code)
        if feature_set is None:
            raise RiskCellNotFoundError(request.cell_code)

        cell = feature_set.cell
        static_features = {
            "elevation_m": cell.elevation_m,
            "slope_deg": cell.slope_deg,
            "aspect_deg": cell.aspect_deg,
        }
        missing_fields = [name for name, value in static_features.items() if value is None]
        if missing_fields:
            raise IncompleteCellFeaturesError(request.cell_code, missing_fields)

        features = ModelFeatures(
            latitude=feature_set.latitude,
            longitude=feature_set.longitude,
            elevation_m=cell.elevation_m,
            slope_deg=cell.slope_deg,
            aspect_deg=cell.aspect_deg,
            rainfall_mm=request.rainfall_mm,
        )
        model_prediction = await self._model_gateway.predict(features)
        risk_level = self._classifier.classify(model_prediction.probability)

        try:
            snapshot = await self._snapshot_repository.save(
                RiskSnapshot(
                    cell_id=cell.id,
                    probability=model_prediction.probability,
                    predicted_class=model_prediction.predicted_class,
                    risk_level=risk_level.value,
                    rainfall_mm=request.rainfall_mm,
                    drivers=model_prediction.drivers,
                )
            )
            alert = await self._alert_service.evaluate(snapshot, cell.cell_code)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        return PredictionResponse(
            snapshot_id=snapshot.id,
            cell_id=cell.id,
            cell_code=cell.cell_code,
            probability=snapshot.probability,
            predicted_class=snapshot.predicted_class,
            risk_level=risk_level,
            rainfall_mm=request.rainfall_mm,
            drivers=snapshot.drivers,
            recorded_at=snapshot.recorded_at,
            alert=alert,
        )
