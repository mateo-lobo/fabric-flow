import math
import unittest

from backend.app.calculations import (
    apply_optimization,
    calculate_cut_result,
    calculate_model,
    optimize_waste,
    validate_model,
)
from backend.app.models import BagModel, Hardware, Piece, Roll


class CalculationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roll = Roll(
            id="fabric-1",
            name="Canvas",
            material="cotton",
            width_cm=100,
            length_m=12,
            price_per_meter=3,
            allows_rotation=False,
            cut_batch_length_m=6,
        )

    def test_calculates_roll_consumption_cost_and_hardware(self) -> None:
        model = BagModel(
            id="model-1",
            name="Tote",
            pieces=[
                Piece(
                    id="body",
                    name="Body",
                    geometry="rectangle",
                    width_cm=20,
                    height_cm=10,
                    quantity=2,
                    material_id="fabric-1",
                )
            ],
            hardware_items=[{"hardwareId": "zipper", "quantity": 3}],
        )
        result = calculate_model(
            model,
            [self.roll],
            batch_size=12,
            hardware=[Hardware(id="zipper", name="Zipper", price_per_unit=2)],
        )

        cut = result["cutResults"][0]
        consumption = result["materialConsumption"][0]
        hardware = result["hardwareConsumption"][0]
        self.assertEqual(cut["totalPiecesPerRoll"], 600)
        self.assertEqual(cut["totalPiecesPerBatch"], 300)
        self.assertEqual(cut["batchesPerRoll"], 2)
        self.assertEqual(cut["consumptionMPerPiece"], 0.02)
        self.assertEqual(cut["efficiency"], 100)
        self.assertEqual(consumption["rollsNeeded"], 1)
        self.assertEqual(consumption["totalCost"], 36)
        self.assertEqual(consumption["cofactor"], 1)
        self.assertEqual(hardware["totalQuantity"], 36)
        self.assertEqual(hardware["totalCost"], 72)
        self.assertEqual(result["totalHardwareCost"], 72)
        self.assertEqual(result["totalCost"], 108)

    def test_rotation_uses_higher_whole_roll_yield(self) -> None:
        roll = Roll(
            id="fabric-1",
            name="Canvas",
            material="cotton",
            width_cm=100,
            length_m=1.2,
            price_per_meter=3,
            allows_rotation=True,
            cut_batch_length_m=1,
        )
        piece = Piece(
            id="panel",
            name="Panel",
            width_cm=60,
            height_cm=40,
            material_id="fabric-1",
        )

        result = calculate_cut_result(piece, roll)

        self.assertEqual(result["orientation"], "rotated")
        self.assertEqual(result["totalPiecesPerRoll"], 4)
        self.assertEqual(result["totalPiecesPerBatch"], 2)
        self.assertEqual(result["wasteWidthCm"], 20)
        self.assertEqual(result["wasteAreaCm2"], 2400)
        self.assertEqual(result["efficiency"], 80)

    def test_directional_pattern_blocks_rotation(self) -> None:
        roll = self.roll.model_copy(update={"allows_rotation": True, "has_directional_pattern": True})
        piece = Piece(
            id="panel",
            name="Panel",
            width_cm=60,
            height_cm=40,
            material_id="fabric-1",
        )

        result = calculate_cut_result(piece, roll)

        self.assertEqual(result["orientation"], "normal")
        self.assertEqual(result["totalPiecesPerRoll"], 30)

    def test_shape_area_and_bounding_dimensions(self) -> None:
        circle = Piece(
            id="circle",
            name="Circle",
            geometry="circle",
            width_cm=20,
            height_cm=20,
            material_id="fabric-1",
        )
        triangle = Piece(
            id="triangle",
            name="Triangle",
            geometry="triangle",
            width_cm=20,
            height_cm=10,
            base_cm=18,
            material_id="fabric-1",
        )

        self.assertAlmostEqual(
            calculate_cut_result(circle, self.roll)["efficiency"],
            math.pi * 100 * 300 / 120_000 * 100,
        )
        triangle_result = calculate_cut_result(triangle, self.roll)
        self.assertEqual(triangle_result["totalPiecesPerRoll"], 600)
        self.assertAlmostEqual(triangle_result["efficiency"], 45)

    def test_validation_matches_legacy_width_fit_rules(self) -> None:
        model = BagModel(
            id="model-1",
            name="Tote",
            pieces=[
                Piece(
                    id="panel",
                    name="Wide panel",
                    width_cm=120,
                    height_cm=40,
                    material_id="fabric-1",
                )
            ],
        )

        rotating_roll = self.roll.model_copy(update={"allows_rotation": True})
        self.assertEqual(validate_model(model, [rotating_roll]), [])
        blocked_roll = self.roll.model_copy(update={"has_directional_pattern": True})
        self.assertEqual(len(validate_model(model, [blocked_roll])), 1)

    def test_waste_optimizer_returns_best_fit_scenario(self) -> None:
        roll = Roll(
            id="fabric-1",
            name="Canvas",
            material="cotton",
            width_cm=100,
            length_m=1,
            price_per_meter=1,
            allows_rotation=False,
            cut_batch_length_m=1,
        )
        model = BagModel(
            id="model-1",
            name="Tote",
            pieces=[
                Piece(
                    id="main",
                    name="Main panel",
                    width_cm=29,
                    height_cm=20,
                    material_id="fabric-1",
                ),
                Piece(
                    id="pocket",
                    name="Pocket",
                    width_cm=10,
                    height_cm=10,
                    quantity=2,
                    material_id="fabric-1",
                ),
            ],
        )
        result = calculate_model(model, [roll], batch_size=1)

        optimization = optimize_waste(model, result["cutResults"], [roll], batch_size=1)
        best = optimization["bestScenario"]

        self.assertEqual(best["pieceId"], "pocket")
        self.assertEqual(best["piecesFitted"], 2)
        self.assertAlmostEqual(best["remainingWasteAreaCm2"], 300)
        self.assertAlmostEqual(best["efficiency"], 1000 / 1300 * 100)
        self.assertAlmostEqual(best["wasteCost"], 0.03)
        self.assertAlmostEqual(optimization["totalSavings"], 0.1)
        self.assertEqual(optimization["totalWasteReduction"], 1000)

        applied = apply_optimization(result, best, model, [roll])
        self.assertAlmostEqual(applied["totalCost"], 1.9)

    def test_legacy_camel_case_inputs_are_accepted(self) -> None:
        roll = Roll.model_validate(
            {
                "id": "fabric-1",
                "name": "Canvas",
                "material": "cotton",
                "widthCm": 100,
                "lengthM": 12,
                "pricePerMeter": 3,
                "allowsRotation": False,
                "hasDirectionalPattern": True,
            }
        )

        self.assertEqual(roll.width_cm, 100)
        self.assertTrue(roll.has_directional_pattern)


if __name__ == "__main__":
    unittest.main()