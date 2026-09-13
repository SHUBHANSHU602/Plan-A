from app.models.asset import Asset


def test_asset_model_has_spatial_and_operational_fields() -> None:
    assert Asset.__tablename__ == "assets"
    assert {
        "asset_code",
        "name",
        "asset_type",
        "criticality",
        "geometry",
        "properties",
    }.issubset(Asset.__table__.columns.keys())

    indexes = {index.name: index for index in Asset.__table__.indexes}
    assert indexes["ix_assets_geometry"].dialect_options["postgresql"]["using"] == "gist"
    assert "ix_assets_type_criticality" in indexes
