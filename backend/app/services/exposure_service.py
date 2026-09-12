from app.repositories.exposure import AssetRepository
from app.repositories.risk import RiskCellRepository
from app.schemas.exposure import AssetType, ExposedAsset, ExposureResponse
from app.services.risk_service import RiskCellNotFoundError


class ExposureService:
    def __init__(
        self,
        cell_repository: RiskCellRepository,
        asset_repository: AssetRepository,
    ) -> None:
        self._cell_repository = cell_repository
        self._asset_repository = asset_repository

    async def get_exposure(self, cell_code: str, radius_m: float) -> ExposureResponse:
        cell = await self._cell_repository.get_by_code(cell_code)
        if cell is None:
            raise RiskCellNotFoundError(cell_code)

        records = await self._asset_repository.find_within_radius(cell.id, radius_m)
        counts = {asset_type: 0 for asset_type in AssetType}
        assets = []

        for record in records:
            asset_type = AssetType(record.asset.asset_type)
            counts[asset_type] += 1
            assets.append(
                ExposedAsset(
                    id=record.asset.id,
                    asset_code=record.asset.asset_code,
                    name=record.asset.name,
                    asset_type=asset_type,
                    criticality=record.asset.criticality,
                    distance_m=record.distance_m,
                    geometry=record.geometry,
                    properties=record.asset.properties,
                )
            )

        return ExposureResponse(
            cell_id=cell.id,
            cell_code=cell.cell_code,
            radius_m=radius_m,
            total_assets=len(assets),
            counts=counts,
            assets=assets,
        )
