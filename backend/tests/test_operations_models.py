from app.models.operations import RainfallObservation, SimulationRun


def test_operational_tables_preserve_queue_and_simulation_state() -> None:
    assert RainfallObservation.__tablename__ == "rainfall_observations"
    assert SimulationRun.__tablename__ == "simulation_runs"
    assert RainfallObservation.__table__.columns.processed_snapshot_id.foreign_keys
    assert SimulationRun.__table__.columns.result_snapshot_id.foreign_keys
    assert any(
        constraint.name == "uq_rainfall_observations_source_event"
        for constraint in RainfallObservation.__table__.constraints
    )
