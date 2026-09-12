"""Notification provider adapters."""

from app.notifications.base import NotificationProvider
from app.notifications.dashboard import DashboardNotificationProvider
from app.notifications.dispatcher import NotificationDispatcher

__all__ = [
    "DashboardNotificationProvider",
    "NotificationDispatcher",
    "NotificationProvider",
]
