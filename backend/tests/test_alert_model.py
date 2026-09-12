from app.models.alert import Alert


def test_alert_model_enforces_one_open_alert_per_cell() -> None:
    indexes = {index.name: index for index in Alert.__table__.indexes}
    open_alert_index = indexes["uq_alerts_open_cell"]

    assert open_alert_index.unique is True
    assert "status IN" in str(open_alert_index.dialect_options["postgresql"]["where"])
    assert "latest_snapshot_id" in Alert.__table__.columns
    assert "occurrence_count" in Alert.__table__.columns
    assert "last_emitted_at" in Alert.__table__.columns
