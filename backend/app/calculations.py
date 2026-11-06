from copy import deepcopy
from datetime import datetime, timezone
from functools import cmp_to_key
from math import ceil, floor, pi
from uuid import uuid4

from .models import BagModel, Hardware, HardwareUse, Piece, Roll


DEFAULT_CUT_BATCH_LENGTH_M = 10.5


def _piece_dimensions(piece: Piece) -> tuple[float, float]:
    if piece.geometry == "circle":
        diameter = (piece.radius_cm or min(piece.width_cm, piece.height_cm) / 2) * 2
        return diameter, diameter
    if piece.geometry == "triangle":
        return piece.base_cm or piece.width_cm, piece.height_cm
    if piece.geometry == "trapezoid":
        return piece.base2_cm or piece.width_cm * 1.5, piece.height_cm
    return piece.width_cm, piece.height_cm


def _piece_area(piece: Piece) -> float:
    if piece.geometry == "circle":
        radius = piece.radius_cm or min(piece.width_cm, piece.height_cm) / 2
        return pi * radius * radius
    if piece.geometry == "triangle":
        base = piece.base_cm or piece.width_cm
        return base * piece.height_cm / 2
    if piece.geometry == "trapezoid":
        base1 = piece.base1_cm or piece.width_cm
        base2 = piece.base2_cm or piece.width_cm * 1.5
        return (base1 + base2) * piece.height_cm / 2
    return piece.width_cm * piece.height_cm


def _grid_fit(piece_width: float, piece_height: float, roll_width: float, roll_length: float) -> dict[str, int]:
    per_row = floor(roll_width / piece_width)
    per_column = floor(roll_length / piece_height)
    return {
        "perRow": per_row,
        "perColumn": per_column,
        "total": per_row * per_column,
    }


def calculate_cut_result(piece: Piece, roll: Roll) -> dict[str, float | int | str]:
    piece_width, piece_height = _piece_dimensions(piece)
    roll_length_cm = roll.length_m * 100
    cut_batch_length_cm = (roll.cut_batch_length_m or DEFAULT_CUT_BATCH_LENGTH_M) * 100

    normal_fit = _grid_fit(piece_width, piece_height, roll.width_cm, roll_length_cm)
    normal_batch_fit = _grid_fit(piece_width, piece_height, roll.width_cm, cut_batch_length_cm)
    rotated_fit = {"perRow": 0, "perColumn": 0, "total": 0}
    rotated_batch_fit = {"perRow": 0, "perColumn": 0, "total": 0}

    if roll.allows_rotation and not roll.has_directional_pattern:
        rotated_fit = _grid_fit(piece_height, piece_width, roll.width_cm, roll_length_cm)
        rotated_batch_fit = _grid_fit(piece_height, piece_width, roll.width_cm, cut_batch_length_cm)

    is_rotated = rotated_fit["total"] > normal_fit["total"]
    selected_fit = rotated_fit if is_rotated else normal_fit
    selected_batch_fit = rotated_batch_fit if is_rotated else normal_batch_fit
    orientation = "rotated" if is_rotated else "normal"
    selected_width, selected_height = (
        (piece_height, piece_width) if is_rotated else (piece_width, piece_height)
    )

    batches_per_roll = floor(roll_length_cm / cut_batch_length_cm)
    waste_width_cm = roll.width_cm - selected_fit["perRow"] * selected_width
    waste_length_cm = roll_length_cm - selected_fit["perColumn"] * selected_height
    waste_area_cm2 = (
        waste_width_cm * roll_length_cm
        + roll.width_cm * waste_length_cm
        - waste_width_cm * waste_length_cm
    )
    consumption_cm_per_piece = (
        roll_length_cm / selected_fit["total"] if selected_fit["total"] > 0 else roll_length_cm
    )
    roll_area_cm2 = roll.width_cm * roll_length_cm
    used_area_cm2 = _piece_area(piece) * selected_fit["total"]

    return {
        "pieceId": piece.id,
        "pieceName": piece.name,
        "orientation": orientation,
        "piecesPerRow": selected_fit["perRow"],
        "piecesPerColumn": selected_fit["perColumn"],
        "totalPiecesPerRoll": selected_fit["total"],
        "totalPiecesPerBatch": selected_batch_fit["total"],
        "batchesPerRoll": batches_per_roll if batches_per_roll > 0 else 1,
        "wasteWidthCm": waste_width_cm,
        "wasteLengthCm": waste_length_cm,
        "wasteAreaCm2": waste_area_cm2,
        "consumptionCmPerPiece": consumption_cm_per_piece,
        "consumptionMPerPiece": consumption_cm_per_piece / 100,
        "efficiency": used_area_cm2 / roll_area_cm2 * 100 if roll_area_cm2 > 0 else 0,
    }


def validate_model(model: BagModel, rolls: list[Roll]) -> list[str]:
    roll_by_id = {roll.id: roll for roll in rolls}
    errors: list[str] = []

    for piece in model.pieces:
        roll = roll_by_id.get(piece.material_id)
        if roll is None:
            errors.append(f'Material não encontrado para peça "{piece.name}"')
            continue

        piece_width, piece_height = _piece_dimensions(piece)
        fits_without_rotation = piece_width <= roll.width_cm
        fits_with_rotation = (
            roll.allows_rotation
            and not roll.has_directional_pattern
            and piece_height <= roll.width_cm
        )
        if not fits_without_rotation and not fits_with_rotation:
            errors.append(
                f'Peça "{piece.name}" ({piece_width}x{piece_height}cm) não cabe '
                f'no rolo "{roll.name}" (largura: {roll.width_cm}cm)'
            )

    return errors


def _material_consumption(
    piece: Piece,
    cut_result: dict[str, float | int | str],
    roll: Roll,
    batch_size: float,
) -> dict[str, float | int | str]:
    required_pieces = piece.quantity * batch_size
    pieces_per_roll = int(cut_result["totalPiecesPerRoll"])
    rolls_needed = ceil(required_pieces / pieces_per_roll) if pieces_per_roll > 0 else 1
    total_length_m = rolls_needed * roll.length_m
    total_cost = total_length_m * roll.price_per_meter

    return {
        "materialId": roll.id,
        "materialName": f"{roll.name} - {roll.material}",
        "totalLengthM": total_length_m,
        "rollsNeeded": rolls_needed,
        "costPerUnit": total_cost / batch_size if batch_size > 0 else total_cost,
        "totalCost": total_cost,
        "cofactor": total_length_m / batch_size if batch_size > 0 else total_length_m,
    }


def _hardware_uses(model: BagModel, hardware: list[Hardware]) -> list[tuple[Hardware, float]]:
    hardware_by_id = {item.id: item for item in hardware}
    uses = model.hardware_items or []

    if not uses:
        uses = [
            HardwareUse(
                hardwareId=hardware_id,
                quantity=(hardware_by_id[hardware_id].quantity_per_product if hardware_id in hardware_by_id else 1),
            )
            for hardware_id in model.hardware_ids or []
        ]

    return [
        (hardware_by_id[use.hardware_id], use.quantity)
        for use in uses
        if use.hardware_id in hardware_by_id
    ]


def calculate_model(
    model: BagModel,
    rolls: list[Roll],
    batch_size: float,
    hardware: list[Hardware] | None = None,
) -> dict[str, object]:
    validation_errors = validate_model(model, rolls)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    rolls_by_id = {roll.id: roll for roll in rolls}
    cut_results: list[dict[str, float | int | str]] = []
    consumption_by_roll: dict[str, dict[str, float | int | str]] = {}

    for piece in model.pieces:
        roll = rolls_by_id[piece.material_id]
        cut_result = calculate_cut_result(piece, roll)
        cut_results.append(cut_result)
        consumption = _material_consumption(piece, cut_result, roll, batch_size)
        existing = consumption_by_roll.get(roll.id)
        if existing is None:
            consumption_by_roll[roll.id] = consumption
        else:
            existing["totalLengthM"] = float(existing["totalLengthM"]) + float(consumption["totalLengthM"])
            existing["rollsNeeded"] = int(existing["rollsNeeded"]) + int(consumption["rollsNeeded"])
            existing["totalCost"] = float(existing["totalCost"]) + float(consumption["totalCost"])
            existing["costPerUnit"] = float(existing["totalCost"]) / batch_size
            existing["cofactor"] = float(existing["totalLengthM"]) / batch_size

    material_consumption = list(consumption_by_roll.values())
    material_cost = sum(float(item["totalCost"]) for item in material_consumption)
    hardware_consumption: list[dict[str, float | str]] = []
    hardware_cost = 0.0

    for item, quantity_per_product in _hardware_uses(model, hardware or []):
        total_quantity = quantity_per_product * batch_size
        total_cost = total_quantity * item.price_per_unit
        hardware_cost += total_cost
        hardware_consumption.append(
            {
                "hardwareId": item.id,
                "hardwareName": item.name,
                "totalQuantity": total_quantity,
                "costPerUnit": total_cost / batch_size if batch_size > 0 else total_cost,
                "totalCost": total_cost,
            }
        )

    result: dict[str, object] = {
        "modelId": model.id,
        "modelName": model.name,
        "batchSize": batch_size,
        "cutResults": cut_results,
        "materialConsumption": material_consumption,
        "totalCost": material_cost + hardware_cost,
        "totalWasteArea": sum(float(item["wasteAreaCm2"]) for item in cut_results),
        "averageEfficiency": (
            sum(float(item["efficiency"]) for item in cut_results) / len(cut_results)
            if cut_results
            else 0
        ),
        "calculatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if hardware_consumption:
        result["hardwareConsumption"] = hardware_consumption
    if hardware_cost > 0:
        result["totalHardwareCost"] = hardware_cost
    return result


def identify_waste_areas(
    cut_results: list[dict[str, object]],
    model: BagModel,
    rolls: list[Roll],
) -> list[dict[str, object]]:
    pieces_by_id = {piece.id: piece for piece in model.pieces}
    rolls_by_id = {roll.id: roll for roll in rolls}
    waste_areas: list[dict[str, object]] = []

    for cut_result in cut_results:
        piece = pieces_by_id.get(str(cut_result["pieceId"]))
        if piece is None:
            continue
        roll = rolls_by_id.get(piece.material_id)
        if roll is None:
            continue

        roll_length_cm = roll.length_m * 100
        cost_per_cm2 = roll.price_per_meter / (roll.width_cm * 100)
        waste_width_cm = float(cut_result["wasteWidthCm"])
        waste_length_cm = float(cut_result["wasteLengthCm"])

        if waste_width_cm > 0:
            waste_areas.append(
                {
                    "id": f"waste-width-{piece.id}",
                    "pieceId": piece.id,
                    "pieceName": str(cut_result["pieceName"]),
                    "materialId": piece.material_id,
                    "widthCm": waste_width_cm,
                    "lengthCm": roll_length_cm,
                    "areaCm2": waste_width_cm * roll_length_cm,
                    "costPerCm2": cost_per_cm2,
                    "rollWidthCm": roll.width_cm,
                    "rollLengthCm": roll_length_cm,
                }
            )
        if waste_length_cm > 0:
            waste_areas.append(
                {
                    "id": f"waste-length-{piece.id}",
                    "pieceId": piece.id,
                    "pieceName": str(cut_result["pieceName"]),
                    "materialId": piece.material_id,
                    "widthCm": roll.width_cm,
                    "lengthCm": waste_length_cm,
                    "areaCm2": roll.width_cm * waste_length_cm,
                    "costPerCm2": cost_per_cm2,
                    "rollWidthCm": roll.width_cm,
                    "rollLengthCm": roll_length_cm,
                }
            )

    return waste_areas


def _calculate_fit_scenario(
    waste: dict[str, object],
    piece: Piece,
    batch_size: float,
) -> dict[str, object] | None:
    piece_width, piece_height = _piece_dimensions(piece)
    waste_width = float(waste["widthCm"])
    waste_length = float(waste["lengthCm"])
    normal_per_row = floor(waste_width / piece_width)
    normal_per_column = floor(waste_length / piece_height)
    normal_total = normal_per_row * normal_per_column
    rotated_per_row = floor(waste_width / piece_height)
    rotated_per_column = floor(waste_length / piece_width)
    rotated_total = rotated_per_row * rotated_per_column
    is_rotated = rotated_total > normal_total

    if is_rotated:
        capacity = rotated_total
        selected_width, selected_height = piece_height, piece_width
        per_row, per_column = rotated_per_row, rotated_per_column
    else:
        capacity = normal_total
        selected_width, selected_height = piece_width, piece_height
        per_row, per_column = normal_per_row, normal_per_column

    if capacity == 0:
        return None

    pieces_fitted = min(capacity, piece.quantity * batch_size)
    used_width = per_row * selected_width
    used_length = per_column * selected_height
    remaining_area = float(waste["areaCm2"]) - used_width * used_length
    waste_cost = remaining_area * float(waste["costPerCm2"])
    efficiency = (
        (float(waste["areaCm2"]) - remaining_area) / float(waste["areaCm2"]) * 100
        if float(waste["areaCm2"]) > 0
        else 0
    )

    return {
        "id": str(uuid4()),
        "wasteId": waste["id"],
        "wastePieceId": waste["pieceId"],
        "wastePieceName": waste["pieceName"],
        "pieceId": piece.id,
        "pieceName": piece.name,
        "piecesFitted": pieces_fitted,
        "remainingWaste": max(0, waste_width - used_width) + max(0, waste_length - used_length),
        "remainingWasteAreaCm2": remaining_area,
        "wasteCost": waste_cost,
        "efficiency": efficiency,
        "materialId": waste["materialId"],
    }


def optimize_waste(
    model: BagModel,
    cut_results: list[dict[str, object]],
    rolls: list[Roll],
    batch_size: float,
) -> dict[str, object]:
    waste_areas = identify_waste_areas(cut_results, model, rolls)
    scenarios: list[dict[str, object]] = []

    for waste in waste_areas:
        if float(waste["widthCm"]) < 5 and float(waste["lengthCm"]) < 5:
            continue
        for piece in model.pieces:
            if piece.material_id != waste["materialId"] or piece.id == waste["pieceId"]:
                continue
            width, height = _piece_dimensions(piece)
            fits = (
                width <= float(waste["widthCm"]) and height <= float(waste["lengthCm"])
            ) or (
                height <= float(waste["widthCm"]) and width <= float(waste["lengthCm"])
            )
            if not fits:
                continue
            scenario = _calculate_fit_scenario(waste, piece, batch_size)
            if scenario is not None and float(scenario["piecesFitted"]) > 0:
                scenarios.append(scenario)

    def compare_scenarios(left: dict[str, object], right: dict[str, object]) -> int:
        cost_difference = float(left["wasteCost"]) - float(right["wasteCost"])
        if abs(cost_difference) > 0.01:
            return -1 if cost_difference < 0 else 1
        efficiency_difference = float(right["efficiency"]) - float(left["efficiency"])
        return -1 if efficiency_difference < 0 else (1 if efficiency_difference > 0 else 0)

    scenarios.sort(key=cmp_to_key(compare_scenarios))
    waste_by_id = {str(waste["id"]): waste for waste in waste_areas}
    total_savings = sum(
        (
            float(waste_by_id[str(scenario["wasteId"])]["areaCm2"])
            - float(scenario["remainingWasteAreaCm2"])
        )
        * float(waste_by_id[str(scenario["wasteId"])]["costPerCm2"])
        for scenario in scenarios
    )
    total_waste_reduction = sum(
        float(waste_by_id[str(scenario["wasteId"])]["areaCm2"])
        - float(scenario["remainingWasteAreaCm2"])
        for scenario in scenarios
    )

    return {
        "scenarios": scenarios,
        "bestScenario": scenarios[0] if scenarios else None,
        "totalSavings": total_savings,
        "totalWasteReduction": total_waste_reduction,
    }


def apply_optimization(
    result: dict[str, object],
    scenario: dict[str, object],
    model: BagModel,
    rolls: list[Roll],
) -> dict[str, object]:
    updated = deepcopy(result)
    material_id = str(scenario["materialId"])
    material = next(
        (item for item in updated.get("materialConsumption", []) if item["materialId"] == material_id),
        None,
    )
    if material is None or not any(roll.id == material_id for roll in rolls):
        return updated

    waste = next(
        (
            item
            for item in identify_waste_areas(
                updated.get("cutResults", []),
                model,
                rolls,
            )
            if item["id"] == scenario["wasteId"]
        ),
        None,
    )
    if waste is None:
        return updated

    used_area = float(waste["areaCm2"]) - float(scenario["remainingWasteAreaCm2"])
    cost_reduction = used_area * float(waste["costPerCm2"])
    material["totalCost"] = float(material["totalCost"]) - cost_reduction
    if float(updated.get("batchSize", 0)) > 0:
        material["costPerUnit"] = float(material["totalCost"]) / float(updated["batchSize"])
    updated["totalCost"] = sum(
        float(item["totalCost"]) for item in updated.get("materialConsumption", [])
    ) + float(updated.get("totalHardwareCost", 0))
    updated["totalWasteArea"] = float(updated.get("totalWasteArea", 0)) - used_area
    updated["appliedOptimization"] = scenario
    updated["calculatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return updated