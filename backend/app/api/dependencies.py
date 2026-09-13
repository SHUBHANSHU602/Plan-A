from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.db.transaction import TransactionManager
from app.notifications.dashboard import DashboardNotificationProvider
from app.notifications.dispatcher import NotificationDispatcher
from app.realtime.alert_hub import alert_websocket_hub
from app.repositories.alert import AlertEventRepository, AlertRepository
from app.repositories.exposure import AssetRepository
from app.repositories.risk import RiskCellRepository, RiskSnapshotRepository
from app.services.alert_management_service import AlertManagementService
from app.services.alert_policy import AlertPolicy
from app.services.alert_service import AlertService
from app.services.exposure_service import ExposureService
from app.services.model_gateway import MockModelGateway, ModelGateway
from app.services.risk_classifier import RiskClassifier, RiskThresholds
from app.services.risk_service import RiskService

model_gateway = MockModelGateway()
notification_dispatcher = NotificationDispatcher(
    [DashboardNotificationProvider(alert_websocket_hub)]
)


def get_model_gateway() -> ModelGateway:
    return model_gateway


def get_risk_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    gateway: Annotated[ModelGateway, Depends(get_model_gateway)],
) -> RiskService:
    settings = get_settings()
    asset_repository = AssetRepository(session)
    classifier = RiskClassifier(
        RiskThresholds(
            medium=settings.risk_medium_threshold,
            high=settings.risk_high_threshold,
            critical=settings.risk_critical_threshold,
        )
    )
    return RiskService(
        cell_repository=RiskCellRepository(session),
        snapshot_repository=RiskSnapshotRepository(session),
        model_gateway=gateway,
        classifier=classifier,
        alert_service=AlertService(
            repository=AlertRepository(session),
            event_repository=AlertEventRepository(session),
            asset_repository=asset_repository,
            policy=AlertPolicy(),
            exposure_radius_m=settings.alert_exposure_radius_m,
            dedup_cooldown=timedelta(minutes=settings.alert_dedup_cooldown_minutes),
        ),
        transaction=TransactionManager(session),
        notification_dispatcher=notification_dispatcher,
    )


def get_exposure_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExposureService:
    return ExposureService(
        cell_repository=RiskCellRepository(session),
        asset_repository=AssetRepository(session),
    )


def get_alert_management_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertManagementService:
    return AlertManagementService(
        alert_repository=AlertRepository(session),
        event_repository=AlertEventRepository(session),
        transaction=TransactionManager(session),
        notification_dispatcher=notification_dispatcher,
    )
