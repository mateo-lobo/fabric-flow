from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="ignore",
        populate_by_name=True,
    )


class Piece(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    geometry: Literal["rectangle", "circle", "triangle", "trapezoid"] = "rectangle"
    width_cm: float = Field(default=10, alias="widthCm", ge=0.1)
    height_cm: float = Field(default=10, alias="heightCm", ge=0.1)
    radius_cm: float | None = Field(default=None, alias="radiusCm", ge=0)
    base_cm: float | None = Field(default=None, alias="baseCm", ge=0)
    base1_cm: float | None = Field(default=None, alias="base1Cm", ge=0)
    base2_cm: float | None = Field(default=None, alias="base2Cm", ge=0)
    quantity: float = Field(default=1, ge=1)
    material_id: str = Field(alias="materialId", min_length=1)


class Roll(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    material: str = Field(min_length=1)
    width_cm: float = Field(alias="widthCm", ge=1, le=500)
    length_m: float = Field(alias="lengthM", ge=0.1, le=1000)
    price_per_meter: float = Field(alias="pricePerMeter", ge=0)
    color: str | None = None
    allows_rotation: bool = Field(default=True, alias="allowsRotation")
    has_directional_pattern: bool = Field(default=False, alias="hasDirectionalPattern")
    cut_batch_length_m: float | None = Field(
        default=None,
        alias="cutBatchLengthM",
        ge=1,
        le=50,
    )


class Hardware(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price_per_unit: float = Field(alias="pricePerUnit", ge=0)
    quantity_per_product: float = Field(default=1, alias="quantityPerProduct", ge=0)


class HardwareUse(DomainModel):
    hardware_id: str = Field(alias="hardwareId", min_length=1)
    quantity: float = Field(default=1, ge=0)


class BagModel(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    pieces: list[Piece] = Field(min_length=1)
    hardware_items: list[HardwareUse] | None = Field(default=None, alias="hardwareItems")
    hardware_ids: list[str] | None = Field(default=None, alias="hardwareIds")
    description: str | None = None


class CalculationRequest(DomainModel):
    model: BagModel
    rolls: list[Roll] = Field(min_length=1)
    hardware: list[Hardware] = Field(default_factory=list)
    batch_size: float = Field(alias="batchSize", ge=1)


class OptimizationScenario(DomainModel):
    waste_id: str = Field(alias="wasteId", min_length=1)
    material_id: str = Field(alias="materialId", min_length=1)
    remaining_waste_area_cm2: float = Field(alias="remainingWasteAreaCm2", ge=0)


class ApplyOptimizationRequest(DomainModel):
    calculation: CalculationRequest
    result: dict[str, Any]
    scenario: OptimizationScenario