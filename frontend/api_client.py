"""HTTP client for the FabricFlow calculation API."""

import os
from typing import Any

import httpx
import streamlit as st


class ApiError(Exception):
    """Raised with a message that is safe to show to the user."""


def base_url() -> str:
    configured = os.environ.get("FABRICFLOW_API_URL")
    if not configured:
        try:
            configured = st.secrets.get("FABRICFLOW_API_URL")
        except st.errors.StreamlitSecretNotFoundError:
            configured = None
    return (configured or "http://127.0.0.1:8000").rstrip("/")


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):
        return "; ".join(
            f"{'.'.join(str(part) for part in item.get('loc', [])[1:])}: {item.get('msg')}"
            for item in detail
        )
    return str(detail or f"API error {response.status_code}")


def _post(path: str, payload: dict[str, Any], timeout: float = 30) -> dict[str, Any]:
    try:
        response = httpx.post(f"{base_url()}{path}", json=payload, timeout=timeout)
    except httpx.HTTPError as error:
        raise ApiError(f"Cannot reach the calculation API at {base_url()}. Is it running?") from error
    if response.is_success:
        return response.json()
    raise ApiError(_detail(response))


def is_up() -> bool:
    try:
        return httpx.get(f"{base_url()}/health", timeout=2).is_success
    except httpx.HTTPError:
        return False


def calculation_payload(
    model: dict[str, Any],
    rolls: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    batch_size: float,
) -> dict[str, Any]:
    """Send only the rolls and hardware the model actually uses."""
    rolls_by_id = {roll["id"]: roll for roll in rolls}
    hardware_by_id = {item["id"]: item for item in hardware}
    missing = [
        piece["name"] for piece in model["pieces"] if piece["materialId"] not in rolls_by_id
    ]
    if missing:
        raise ApiError(f"These pieces use a roll that no longer exists: {', '.join(missing)}")

    roll_ids = {piece["materialId"] for piece in model["pieces"]}
    hardware_ids = {use["hardwareId"] for use in model.get("hardwareItems") or []}
    return {
        "model": model,
        "rolls": [rolls_by_id[roll_id] for roll_id in roll_ids],
        "hardware": [hardware_by_id[item] for item in hardware_ids if item in hardware_by_id],
        "batchSize": batch_size,
    }


def calculate(
    model: dict[str, Any],
    rolls: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    batch_size: float,
) -> dict[str, Any]:
    request = calculation_payload(model, rolls, hardware, batch_size)
    response = _post("/api/calculate", request)
    return {"request": request, **response}


def apply_scenario(calculation: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    return _post(
        "/api/calculate/apply-optimization",
        {
            "calculation": calculation["request"],
            "result": calculation["result"],
            "scenario": scenario,
        },
    )


def chat(session_id: str, message: str) -> dict[str, Any]:
    return _post("/api/agent/chat", {"sessionId": session_id, "message": message}, timeout=120)
