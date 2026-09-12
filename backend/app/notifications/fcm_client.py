import asyncio
from typing import Protocol

import firebase_admin
from firebase_admin import messaging

from app.schemas.notification import NotificationEvent


class PushDeliveryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        invalid_target: bool = False,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.invalid_target = invalid_target


class PushClient(Protocol):
    async def send(self, registration_id: str, event: NotificationEvent) -> str: ...


class FirebaseAdminClient:
    _INVALID_TARGET_ERRORS = {"SenderIdMismatchError", "UnregisteredError"}
    _RETRYABLE_ERRORS = {
        "InternalError",
        "QuotaExceededError",
        "ResourceExhaustedError",
        "ServerUnavailableError",
        "UnavailableError",
    }

    def __init__(self, project_id: str, request_timeout_seconds: int) -> None:
        app_name = "plan-a-fcm"
        try:
            self._app = firebase_admin.get_app(app_name)
        except ValueError:
            self._app = firebase_admin.initialize_app(
                options={
                    "projectId": project_id,
                    "httpTimeout": request_timeout_seconds,
                },
                name=app_name,
            )

    async def send(self, registration_id: str, event: NotificationEvent) -> str:
        title = str(event.payload.get("title", "Landslide risk alert"))
        body = str(event.payload.get("message", "A landslide risk alert was updated."))
        data = {
            "event_id": str(event.event_id),
            "alert_id": str(event.alert_id),
            "event_type": event.event_type.value,
        }
        for key in ("cell_code", "severity", "status"):
            if key in event.payload:
                data[key] = str(event.payload[key])

        message = messaging.Message(
            fid=registration_id,
            notification=messaging.Notification(title=title, body=body),
            data=data,
        )
        try:
            return await asyncio.to_thread(messaging.send, message, app=self._app)
        except Exception as error:
            error_name = type(error).__name__
            invalid_target = error_name in self._INVALID_TARGET_ERRORS
            raise PushDeliveryError(
                str(error),
                retryable=error_name in self._RETRYABLE_ERRORS,
                invalid_target=invalid_target,
            ) from error
