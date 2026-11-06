import os
import unittest
from unittest.mock import patch

import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from backend.app.agent import agent as agent_module
from backend.app.agent.state import Session, store
from backend.app.agent.tools import build_tools
from backend.app.main import app


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model that accepts tool binding and replays scripted messages."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def tools_by_name(session: Session) -> dict:
    return {item.name: item for item in build_tools(session)}


ROLL = {
    "name": "Canvas",
    "material": "cotton",
    "width_cm": 100,
    "length_m": 1,
    "price_per_meter": 2,
    "allows_rotation": False,
    "cut_batch_length_m": 1,
}


class AgentToolTests(unittest.TestCase):
    def test_tools_build_draft_and_match_direct_calculation(self) -> None:
        session = Session()
        tools = tools_by_name(session)
        tools["add_roll"].invoke(ROLL)
        tools["add_hardware"].invoke({"name": "Zipper", "price_per_unit": 0.5, "quantity_per_bag": 3})
        tools["add_piece"].invoke(
            {"name": "Main panel", "roll_id": "canvas", "width_cm": 29, "height_cm": 20}
        )
        tools["add_piece"].invoke(
            {"name": "Pocket", "roll_id": "canvas", "width_cm": 10, "height_cm": 10, "quantity_per_bag": 2}
        )
        tools["set_model_and_batch"].invoke({"model_name": "Tote bag", "batch_size": 2})

        summary = tools["run_calculation"].invoke({})

        self.assertAlmostEqual(summary["totalCost"], 7.0)
        self.assertAlmostEqual(summary["totalHardwareCost"], 3.0)
        self.assertAlmostEqual(summary["averageEfficiencyPercent"], 93.5)

    def test_incomplete_draft_and_bad_input_return_messages(self) -> None:
        tools = tools_by_name(Session())

        self.assertIn("Draft incomplete", tools["run_calculation"].invoke({}))
        self.assertIn("Unknown roll_id", tools["add_piece"].invoke(
            {"name": "Panel", "roll_id": "missing", "width_cm": 10, "height_cm": 10}
        ))
        self.assertIn("Invalid roll", tools["add_roll"].invoke({**ROLL, "width_cm": 0}))

    def test_piece_wider_than_roll_is_reported(self) -> None:
        session = Session()
        tools = tools_by_name(session)
        tools["add_roll"].invoke(ROLL)
        tools["add_piece"].invoke(
            {"name": "Wide", "roll_id": "canvas", "width_cm": 150, "height_cm": 150}
        )
        tools["set_model_and_batch"].invoke({"model_name": "Tote", "batch_size": 1})

        self.assertIn("não cabe", tools["run_calculation"].invoke({}))

    def test_compare_alternative_reports_cost_difference(self) -> None:
        session = Session()
        tools = tools_by_name(session)
        tools["add_roll"].invoke(ROLL)
        tools["add_piece"].invoke(
            {"name": "Pocket", "roll_id": "canvas", "width_cm": 10, "height_cm": 10, "quantity_per_bag": 2}
        )
        tools["set_model_and_batch"].invoke({"model_name": "Tote", "batch_size": 2})

        comparison = tools["compare_alternative"].invoke({"roll_id": "canvas", "new_price_per_meter": 3})

        self.assertAlmostEqual(comparison["costDifference"], 1.0)
        self.assertEqual(session.rolls["canvas"].price_per_meter, 2)


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        store.clear()

    def test_agent_loop_runs_tools_and_returns_reply(self) -> None:
        model = ScriptedModel(
            messages=iter(
                [
                    call("add_roll", ROLL, "1"),
                    call("add_piece", {"name": "Pocket", "roll_id": "canvas", "width_cm": 10, "height_cm": 10}, "2"),
                    call("set_model_and_batch", {"model_name": "Tote", "batch_size": 1}, "3"),
                    call("run_calculation", {}, "4"),
                    AIMessage(content="Custo total calculado."),
                ]
            )
        )

        response = agent_module.run_chat("s1", "Quero uma bolsa", model=model)

        self.assertEqual(response["reply"], "Custo total calculado.")
        self.assertEqual(response["draft"]["pieces"][0]["name"], "Pocket")
        self.assertAlmostEqual(response["result"]["totalCost"], 2.0)

    def test_chat_endpoint_returns_503_without_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            response = TestClient(app).post("/api/agent/chat", json={"sessionId": "s", "message": "oi"})

        self.assertEqual(response.status_code, 503)

    def test_provider_quota_error_becomes_readable_502(self) -> None:
        response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com"))
        quota = openai.RateLimitError("insufficient_quota", response=response, body=None)

        self.assertIn("no credits", agent_module.explain_provider_error(quota))
        with patch.object(agent_module, "run_chat", side_effect=agent_module.UpstreamError("no credits")):
            reply = TestClient(app).post("/api/agent/chat", json={"sessionId": "s", "message": "oi"})

        self.assertEqual((reply.status_code, reply.json()["detail"]), (502, "no credits"))


if __name__ == "__main__":
    unittest.main()
