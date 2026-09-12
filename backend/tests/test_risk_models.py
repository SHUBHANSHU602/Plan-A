from app.models.risk import RiskCell, RiskSnapshot


def test_risk_tables_keep_static_and_dynamic_data_separate() -> None:
    assert RiskCell.__tablename__ == "risk_cells"
    assert RiskSnapshot.__tablename__ == "risk_snapshots"
    assert "probability" not in RiskCell.__table__.columns
    assert "probability" in RiskSnapshot.__table__.columns
    assert "risk_level" in RiskSnapshot.__table__.columns
    assert "rainfall_mm" in RiskSnapshot.__table__.columns
    assert RiskSnapshot.__table__.columns.cell_id.foreign_keys
