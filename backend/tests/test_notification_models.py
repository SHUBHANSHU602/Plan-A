from app.models.notification import AlertDelivery, NotificationSubscription


def test_notification_tables_have_delivery_safety_constraints() -> None:
    assert NotificationSubscription.__tablename__ == "notification_subscriptions"
    assert AlertDelivery.__tablename__ == "alert_deliveries"
    assert AlertDelivery.__table__.columns.alert_event_id.foreign_keys
    assert AlertDelivery.__table__.columns.subscription_id.foreign_keys
    assert any(
        constraint.name == "uq_notification_subscriptions_registration_id_hash"
        for constraint in NotificationSubscription.__table__.constraints
    )
    assert any(
        constraint.name == "uq_alert_deliveries_event_subscription_provider"
        for constraint in AlertDelivery.__table__.constraints
    )
