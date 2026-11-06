import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FRONTEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRONTEND))
sys.path.insert(0, str(FRONTEND.parent))

from fastapi.testclient import TestClient  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import api_client  # noqa: E402
import catalog  # noqa: E402
import i18n  # noqa: E402
import pieces  # noqa: E402
from backend.app.main import app as backend_app  # noqa: E402

ROLL = {
    "id": "canvas",
    "name": "Canvas",
    "material": "cotton",
    "widthCm": 100,
    "lengthM": 1,
    "pricePerMeter": 2,
    "allowsRotation": False,
    "hasDirectionalPattern": False,
    "cutBatchLengthM": 1,
}
MODEL = {
    "id": "tote",
    "name": "Tote bag",
    "description": "",
    "pieces": [
        {"id": "main", "name": "Main panel", "geometry": "rectangle", "widthCm": 29,
         "heightCm": 20, "quantity": 1, "materialId": "canvas"},
        {"id": "pocket", "name": "Pocket", "geometry": "rectangle", "widthCm": 10,
         "heightCm": 10, "quantity": 2, "materialId": "canvas"},
    ],
    "hardwareItems": [{"hardwareId": "zipper", "quantity": 3}],
}
ZIPPER = {"id": "zipper", "name": "Zipper", "pricePerUnit": 0.5, "quantityPerProduct": 1}


class IsolatedCatalog(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        patcher = patch.dict(os.environ, {"FABRICFLOW_DATA": str(Path(self.directory.name) / "c.json")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.directory.cleanup)

    def seed(self) -> None:
        catalog.upsert("rolls", ROLL)
        catalog.upsert("hardware", ZIPPER)
        catalog.upsert("models", MODEL)


class CatalogTests(IsolatedCatalog):
    def test_upsert_update_and_delete(self) -> None:
        saved = catalog.upsert("rolls", {**ROLL, "id": None})
        self.assertTrue(saved["id"])
        catalog.upsert("rolls", {**saved, "name": "Renamed"})

        self.assertEqual([roll["name"] for roll in catalog.load()["rolls"]], ["Renamed"])
        catalog.delete("rolls", saved["id"])
        self.assertEqual(catalog.load()["rolls"], [])

    def test_usage_lookups_block_deletion_candidates(self) -> None:
        self.seed()

        self.assertEqual(catalog.models_using_roll("canvas"), ["Tote bag"])
        self.assertEqual(catalog.models_using_hardware("zipper"), ["Tote bag"])
        self.assertEqual(catalog.models_using_roll("other"), [])

    def test_importing_assistant_draft_twice_does_not_duplicate(self) -> None:
        draft = {
            "modelName": "Tote",
            "rolls": [ROLL],
            "hardware": [ZIPPER],
            "hardwareUses": [{"hardwareId": "zipper", "quantity": 3}],
            "pieces": MODEL["pieces"],
        }

        catalog.import_draft(draft)
        counts = catalog.import_draft(draft)

        data = catalog.load()
        self.assertEqual(counts, {"rolls": 1, "hardware": 1, "models": 1})
        self.assertEqual((len(data["rolls"]), len(data["hardware"]), len(data["models"])), (1, 1, 1))

    def test_duplicate_roll_labels_are_disambiguated(self) -> None:
        labels = catalog.roll_labels([ROLL, {**ROLL, "id": "canvas-2"}])

        self.assertEqual(len(set(labels.values())), 2)


class PieceTests(unittest.TestCase):
    def test_circle_and_trapezoid_map_to_api_fields(self) -> None:
        circle = pieces.build_piece("circle", "Base", "r", 1, radius=5)
        trapezoid = pieces.build_piece("trapezoid", "Side", "r", 2, base1=10, base2=20, height=8)

        self.assertEqual((circle["radiusCm"], circle["widthCm"], circle["heightCm"]), (5, 10, 10))
        self.assertEqual((trapezoid["base1Cm"], trapezoid["base2Cm"], trapezoid["heightCm"]), (10, 20, 8))

    def test_invalid_pieces_raise_readable_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "name"):
            pieces.build_piece("rectangle", " ", "r", 1, width=1, height=1)
        with self.assertRaisesRegex(ValueError, "larger base"):
            pieces.build_piece("trapezoid", "Side", "r", 1, base1=20, base2=10, height=5)

    def test_describe_includes_size_and_quantity(self) -> None:
        text = pieces.describe(MODEL["pieces"][0])

        self.assertIn("29 x 20 cm", text)
        self.assertIn("1 per bag", text)


class LocalizationTests(unittest.TestCase):
    def test_portuguese_translation_and_english_fallback(self) -> None:
        with patch.object(i18n, "language", return_value="Português"):
            self.assertEqual(i18n.t("Start a calculation"), "Iniciar um cálculo")
            self.assertEqual(i18n.t("Untranslated model name"), "Untranslated model name")

    def test_dashboard_renders_the_portuguese_tutorial(self) -> None:
        at = AppTest.from_file(str(FRONTEND / "app_pages" / "dashboard.py"), default_timeout=60)
        at.session_state["language"] = "Português"
        at.run()

        self.assertFalse(at.exception, [item.value for item in at.exception])
        self.assertIn("Do rolo de tecido ao plano de corte", [item.value for item in at.header])
        self.assertIn("Seu fluxo de trabalho", [item.value for item in at.subheader])


class ApiClientTests(unittest.TestCase):
    def test_api_url_uses_environment_then_streamlit_secret(self) -> None:
        with patch.dict(os.environ, {"FABRICFLOW_API_URL": "https://env.example/"}, clear=True):
            self.assertEqual(api_client.base_url(), "https://env.example")
        with patch.dict(os.environ, {"FABRICFLOW_API_URL": "fabricflow-api:10000"}, clear=True):
            self.assertEqual(api_client.base_url(), "http://fabricflow-api:10000")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(api_client.st, "secrets", {"FABRICFLOW_API_URL": "https://cloud.example/"}),
        ):
            self.assertEqual(api_client.base_url(), "https://cloud.example")

    def test_calculation_allows_backend_cold_start(self) -> None:
        with patch.object(
            api_client, "_post", return_value={"result": {}, "optimization": {}}
        ) as post:
            api_client.calculate(MODEL, [ROLL], [ZIPPER], 1)

        self.assertEqual(post.call_args.kwargs["timeout"], 120)

    def test_payload_contains_only_used_rolls_and_hardware(self) -> None:
        payload = api_client.calculation_payload(
            MODEL, [ROLL, {**ROLL, "id": "unused"}], [ZIPPER, {**ZIPPER, "id": "unused"}], 5
        )

        self.assertEqual([roll["id"] for roll in payload["rolls"]], ["canvas"])
        self.assertEqual([item["id"] for item in payload["hardware"]], ["zipper"])

    def test_missing_roll_gives_user_message(self) -> None:
        with self.assertRaisesRegex(api_client.ApiError, "no longer exists"):
            api_client.calculation_payload(MODEL, [], [], 5)


def backend_post(path: str, payload: dict, timeout: float = 30) -> dict:
    response = TestClient(backend_app).post(path, json=payload)
    if not response.is_success:
        raise api_client.ApiError(str(response.json().get("detail")))
    return response.json()


class PageTests(IsolatedCatalog):
    def page(self, name: str) -> AppTest:
        return AppTest.from_file(str(FRONTEND / "app_pages" / name), default_timeout=20)

    def test_pages_render_empty_catalog_without_errors(self) -> None:
        for name in ("dashboard.py", "rolls.py", "hardware.py", "models.py", "history.py", "calculator.py"):
            with self.subTest(page=name):
                at = self.page(name).run()
                self.assertFalse(at.exception, [item.value for item in at.exception])

    def test_calculator_runs_end_to_end_against_backend(self) -> None:
        self.seed()
        with patch.object(api_client, "_post", backend_post):
            at = self.page("calculator.py").run()
            at.number_input(key="calc_batch").set_value(2)
            next(button for button in at.button if button.label == "Calculate").click().run()

        self.assertFalse(at.exception, [item.value for item in at.exception])
        metrics = {metric.label: metric.value for metric in at.metric}
        self.assertEqual(metrics["Total cost"], "R$ 7.00")
        self.assertEqual(metrics["Average efficiency"], "93.5%")

    def test_calculator_shows_api_errors(self) -> None:
        self.seed()

        def offline(path: str, payload: dict, timeout: float = 30) -> dict:
            raise api_client.ApiError("Cannot reach the calculation API")

        with patch.object(api_client, "_post", offline):
            at = self.page("calculator.py").run()
            next(button for button in at.button if button.label == "Calculate").click().run()

        self.assertIn("Cannot reach", at.error[0].value)

    def test_calculator_results_follow_portuguese_language_setting(self) -> None:
        self.seed()
        model = catalog.load()["models"][0]
        model["hardwareItems"] = []
        catalog.upsert("models", model)
        with patch.object(api_client, "_post", backend_post):
            at = self.page("calculator.py")
            at.session_state["language"] = "Português"
            at.run()
            at.number_input(key="calc_batch").set_value(2)
            next(button for button in at.button if button.label == "Calcular").click().run()

        self.assertFalse(at.exception, [item.value for item in at.exception])
        metrics = {metric.label: metric.value for metric in at.metric}
        self.assertEqual(metrics["Custo total"], "R$ 4,00")
        self.assertEqual(metrics["Eficiência média"], "93.5%")
        self.assertIn("Consumo por material", [item.value for item in at.subheader])

    def test_history_lists_saved_calculation(self) -> None:
        catalog.upsert(
            "history",
            {
                "id": "h1", "name": "Run 1", "modelName": "Tote", "batchSize": 2,
                "savedAt": "2026-01-01T10:00:00",
                "result": {"totalCost": 7.0, "averageEfficiency": 93.5},
            },
        )

        at = self.page("history.py").run()

        self.assertFalse(at.exception, [item.value for item in at.exception])


if __name__ == "__main__":
    unittest.main()
