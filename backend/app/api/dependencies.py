from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.db.transaction import TransactionManager
from app.notifications.dashboard import DashboardNotificationProvider
from app.notifications.dispatcher import NotificationDispatcher
from app.notifications.fcm import FcmNotificationProvider
from app.notifications.fcm_client import FirebaseAdminClient
from app.realtime.alert_hub import alert_websocket_hub
from app.repositories.alert import AlertEventRepository, AlertRepository
from app.repositories.exposure import AssetRepository
from app.repositories.notification import (
    AlertDeliveryRepository,
    NotificationSubscriptionRepository,
)
from app.repositories.operations import RainfallObservationRepository, SimulationRunRepository
from app.repositories.risk import RiskCellRepository, RiskSnapshotRepository
from app.services.alert_management_service import AlertManagementService
from app.services.alert_policy import AlertPolicy
from app.services.alert_service import AlertService
from app.services.delivery_query_service import DeliveryQueryService
from app.services.exposure_service import ExposureService
from app.services.fcm_delivery_service import FcmDeliveryService
from app.services.model_gateway import MockModelGateway, ModelGateway
from app.services.notification_subscription_service import NotificationSubscriptionService
from app.services.rainfall_ingestion_service import RainfallIngestionService
from app.services.rainfall_processing_service import RainfallProcessingService
from app.services.risk_classifier import RiskClassifier, RiskThresholds
from app.services.risk_service import RiskService
from app.services.simulation_service import SimulationService

settings = get_settings()
model_gateway = MockModelGateway()
firebase_client = (
    FirebaseAdminClient(settings.fcm_project_id, settings.fcm_request_timeout_seconds)
    if settings.fcm_enabled and settings.fcm_project_id
    else None
)


def build_notification_dispatcher(session: AsyncSession) -> NotificationDispatcher:
    providers = [DashboardNotificationProvider(alert_websocket_hub)]
    if firebase_client is not None:
        providers.append(FcmNotificationProvider(build_fcm_delivery_service(session)))
    return NotificationDispatcher(providers)


def build_fcm_delivery_service(session: AsyncSession) -> FcmDeliveryService:
    if firebase_client is None:
        raise RuntimeError("FCM is disabled")
    return FcmDeliveryService(
        subscription_repository=NotificationSubscriptionRepository(session),
        delivery_repository=AlertDeliveryRepository(session),
        transaction=TransactionManager(session),
        client=firebase_client,
        max_attempts=settings.fcm_max_attempts,
        retry_base_seconds=settings.fcm_retry_base_seconds,
    )


def build_risk_service(
    session: AsyncSession,
    gateway: ModelGateway | None = None,
) -> RiskService:
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
        model_gateway=gateway or model_gateway,
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
        notification_dispatcher=build_notification_dispatcher(session),
    )


def get_model_gateway() -> ModelGateway:
    return model_gateway


def get_risk_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    gateway: Annotated[ModelGateway, Depends(get_model_gateway)],
) -> RiskService:
    return build_risk_service(session, gateway)


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
        notification_dispatcher=build_notification_dispatcher(session),
    )


def get_notification_subscription_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationSubscriptionService:
    return NotificationSubscriptionService(
        repository=NotificationSubscriptionRepository(session),
        transaction=TransactionManager(session),
    )


def get_delivery_query_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DeliveryQueryService:
    return DeliveryQueryService(AlertDeliveryRepository(session))


def get_rainfall_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RainfallIngestionService:
    return RainfallIngestionService(
        cell_repository=RiskCellRepository(session),
        observation_repository=RainfallObservationRepository(session),
        transaction=TransactionManager(session),
    )


def build_rainfall_processing_service(session: AsyncSession) -> RainfallProcessingService:
    return RainfallProcessingService(
        observation_repository=RainfallObservationRepository(session),
        cell_repository=RiskCellRepository(session),
        risk_service=build_risk_service(session),
        transaction=TransactionManager(session),
        max_attempts=settings.rainfall_processing_max_attempts,
        retry_seconds=settings.rainfall_processing_retry_seconds,
        claim_timeout_seconds=settings.rainfall_processing_claim_timeout_seconds,
    )


def get_simulation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SimulationService:
    return SimulationService(
        cell_repository=RiskCellRepository(session),
        snapshot_repository=RiskSnapshotRepository(session),
        run_repository=SimulationRunRepository(session),
        risk_service=build_risk_service(session),
        transaction=TransactionManager(session),
    )
