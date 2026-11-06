from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from ..calculations import apply_optimization, calculate_model, optimize_waste
from ..models import Hardware, HardwareUse, Piece, Roll
from .state import Session, slugify


def _validation_message(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    )


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "totalCost": result["totalCost"],
        "averageEfficiencyPercent": result["averageEfficiency"],
        "totalWasteAreaCm2": result["totalWasteArea"],
        "materials": [
            {
                "name": item["materialName"],
                "rollsNeeded": item["rollsNeeded"],
                "totalLengthM": item["totalLengthM"],
                "totalCost": item["totalCost"],
                "costPerUnit": item["costPerUnit"],
            }
            for item in result["materialConsumption"]
        ],
        "pieces": [
            {
                "name": item["pieceName"],
                "orientation": item["orientation"],
                "piecesPerRoll": item["totalPiecesPerRoll"],
                "efficiencyPercent": item["efficiency"],
            }
            for item in result["cutResults"]
        ],
    }
    if "totalHardwareCost" in result:
        summary["totalHardwareCost"] = result["totalHardwareCost"]
    return summary


def build_tools(session: Session) -> list[BaseTool]:
    """Tools bound to one session; they only wrap the existing calculation functions."""

    @tool
    def add_roll(
        name: str,
        material: str,
        width_cm: float,
        length_m: float,
        price_per_meter: float,
        allows_rotation: bool = True,
        has_directional_pattern: bool = False,
        cut_batch_length_m: float | None = None,
    ) -> str:
        """Register a fabric roll (width in cm, length in m, price in R$ per linear meter). Returns its roll_id."""
        roll_id = slugify(name)
        try:
            session.rolls[roll_id] = Roll(
                id=roll_id,
                name=name,
                material=material,
                widthCm=width_cm,
                lengthM=length_m,
                pricePerMeter=price_per_meter,
                allowsRotation=allows_rotation,
                hasDirectionalPattern=has_directional_pattern,
                cutBatchLengthM=cut_batch_length_m,
            )
        except ValidationError as error:
            return f"Invalid roll: {_validation_message(error)}"
        return f"Roll saved with roll_id={roll_id}"

    @tool
    def add_hardware(name: str, price_per_unit: float, quantity_per_bag: float = 1) -> str:
        """Register a hardware item (zipper, buckle...) with price in R$ and how many go in one bag."""
        hardware_id = slugify(name)
        try:
            session.hardware[hardware_id] = Hardware(
                id=hardware_id,
                name=name,
                pricePerUnit=price_per_unit,
                quantityPerProduct=quantity_per_bag,
            )
            session.hardware_uses = [
                use for use in session.hardware_uses if use.hardware_id != hardware_id
            ]
            session.hardware_uses.append(
                HardwareUse(hardwareId=hardware_id, quantity=quantity_per_bag)
            )
        except ValidationError as error:
            return f"Invalid hardware: {_validation_message(error)}"
        return f"Hardware saved with hardware_id={hardware_id}"

    @tool
    def add_piece(
        name: str,
        roll_id: str,
        width_cm: float,
        height_cm: float,
        quantity_per_bag: float = 1,
        geometry: Literal["rectangle", "circle", "triangle", "trapezoid"] = "rectangle",
        radius_cm: float | None = None,
        base_cm: float | None = None,
        base1_cm: float | None = None,
        base2_cm: float | None = None,
    ) -> str:
        """Add a pattern piece cut from the roll roll_id. Dimensions in cm; circles use radius_cm."""
        if roll_id not in session.rolls:
            return f"Unknown roll_id '{roll_id}'. Known rolls: {list(session.rolls)}"
        try:
            piece = Piece(
                id=slugify(name),
                name=name,
                geometry=geometry,
                widthCm=width_cm,
                heightCm=height_cm,
                radiusCm=radius_cm,
                baseCm=base_cm,
                base1Cm=base1_cm,
                base2Cm=base2_cm,
                quantity=quantity_per_bag,
                materialId=roll_id,
            )
        except ValidationError as error:
            return f"Invalid piece: {_validation_message(error)}"
        session.pieces = [item for item in session.pieces if item.id != piece.id] + [piece]
        return f"Piece saved with piece_id={piece.id}"

    @tool
    def set_model_and_batch(model_name: str, batch_size: float) -> str:
        """Set the bag model name and how many bags will be produced (batch size)."""
        if batch_size < 1:
            return "Invalid batch_size: must be at least 1"
        session.model_name = model_name
        session.batch_size = batch_size
        return "Saved"

    @tool
    def show_draft() -> dict[str, Any]:
        """Return everything collected so far, to check what is still missing."""
        return session.draft()

    @tool
    def run_calculation() -> dict[str, Any] | str:
        """Calculate fabric consumption, cost, efficiency and scrap-reuse opportunities for the current draft."""
        try:
            request = session.build_request()
            result = calculate_model(request.model, request.rolls, request.batch_size, request.hardware)
        except ValidationError as error:
            return f"Draft incomplete: {_validation_message(error)}"
        except ValueError as error:
            return f"Cannot calculate: {error}"

        optimization = optimize_waste(request.model, result["cutResults"], request.rolls, request.batch_size)
        session.last_result = result
        session.last_optimization = optimization
        summary = _summary(result)
        summary["scrapScenarios"] = [
            {
                "index": index,
                "fitPiece": scenario["pieceName"],
                "piecesFitted": scenario["piecesFitted"],
                "fromScrapOf": scenario["wastePieceName"],
            }
            for index, scenario in enumerate(optimization["scenarios"][:5])
        ]
        summary["scrapSavings"] = optimization["totalSavings"]
        return summary

    @tool
    def apply_scrap_scenario(index: int) -> dict[str, Any] | str:
        """Apply scrap scenario number `index` from the last calculation and return the updated totals."""
        if session.last_result is None or session.last_optimization is None:
            return "Run run_calculation first"
        scenarios = session.last_optimization["scenarios"]
        if not 0 <= index < len(scenarios):
            return f"Index out of range (0..{len(scenarios) - 1})"
        request = session.build_request()
        updated = apply_optimization(session.last_result, scenarios[index], request.model, request.rolls)
        session.last_result = updated
        return _summary(updated)

    @tool
    def compare_alternative(
        roll_id: str,
        new_width_cm: float | None = None,
        new_price_per_meter: float | None = None,
        allows_rotation: bool | None = None,
        new_batch_size: float | None = None,
    ) -> dict[str, Any] | str:
        """What-if: recalculate with a changed roll width/price/rotation or batch size without altering the draft."""
        if roll_id not in session.rolls:
            return f"Unknown roll_id '{roll_id}'. Known rolls: {list(session.rolls)}"
        try:
            base = session.build_request()
            changes: dict[str, Any] = {}
            if new_width_cm is not None:
                changes["width_cm"] = new_width_cm
            if new_price_per_meter is not None:
                changes["price_per_meter"] = new_price_per_meter
            if allows_rotation is not None:
                changes["allows_rotation"] = allows_rotation
            rolls = [
                roll.model_copy(update=changes) if roll.id == roll_id else roll for roll in base.rolls
            ]
            batch = new_batch_size or base.batch_size
            baseline = calculate_model(base.model, base.rolls, base.batch_size, base.hardware)
            alternative = calculate_model(base.model, rolls, batch, base.hardware)
        except ValidationError as error:
            return f"Draft incomplete: {_validation_message(error)}"
        except ValueError as error:
            return f"Cannot calculate: {error}"
        return {
            "baseline": _summary(baseline),
            "alternative": _summary(alternative),
            "costDifference": alternative["totalCost"] - baseline["totalCost"],
            "costPerUnitDifference": alternative["totalCost"] / batch
            - baseline["totalCost"] / base.batch_size,
        }

    return [
        add_roll,
        add_hardware,
        add_piece,
        set_model_and_batch,
        show_draft,
        run_calculation,
        apply_scrap_scenario,
        compare_alternative,
    ]
