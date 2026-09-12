from app.db.transaction import TransactionManager
from app.models.risk import RiskSnapshot
from app.notifications.dispatcher import NotificationDispatcher
from app.repositories.risk import RiskCellRepository, RiskSnapshotRepository
from app.schemas.alert import AlertAction, AlertEventType
from app.schemas.notification import NotificationEvent
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
        notification_dispatcher: NotificationDispatcher,
    ) -> None:
        self._cell_repository = cell_repository
        self._snapshot_repository = snapshot_repository
        self._model_gateway = model_gateway
        self._classifier = classifier
        self._alert_service = alert_service
        self._transaction = transaction
        self._notification_dispatcher = notification_dispatcher

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
        notification_event = None

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
            if alert is not None and alert.action != AlertAction.SUPPRESSED:
                if alert.event_id is None or alert.event_created_at is None:
                    raise RuntimeError("emitted alert is missing its audit event")
                notification_event = NotificationEvent(
                    event_id=alert.event_id,
                    alert_id=alert.alert_id,
                    event_type=AlertEventType(alert.action.value),
                    occurred_at=alert.event_created_at,
                    payload={
                        "cell_id": str(cell.id),
                        "cell_code": cell.cell_code,
                        "severity": alert.severity.value,
                        "status": "ACTIVE",
                        "probability": snapshot.probability,
                        "drivers": snapshot.drivers,
                        "title": alert.title,
                        "message": alert.message,
                    },
                )
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        if notification_event is not None:
            await self._notification_dispatcher.dispatch(notification_event)

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
