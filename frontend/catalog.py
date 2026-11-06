"""Local JSON storage for rolls, hardware, bag models and calculation history."""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

COLLECTIONS = ("rolls", "hardware", "models", "history")


def data_path() -> Path:
    override = os.environ.get("FABRICFLOW_DATA")
    return Path(override) if override else Path(__file__).parent / "data" / "catalog.json"


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def load() -> dict[str, list[dict[str, Any]]]:
    path = data_path()
    stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {name: list(stored.get(name, [])) for name in COLLECTIONS}


def _save(data: dict[str, list[dict[str, Any]]]) -> None:
    path = data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def upsert(collection: str, item: dict[str, Any]) -> dict[str, Any]:
    data = load()
    saved = {**item, "id": item.get("id") or new_id()}
    items = data[collection]
    for index, existing in enumerate(items):
        if existing["id"] == saved["id"]:
            items[index] = saved
            break
    else:
        items.append(saved)
    _save(data)
    return saved


def delete(collection: str, item_id: str) -> None:
    data = load()
    data[collection] = [item for item in data[collection] if item["id"] != item_id]
    _save(data)


def roll_labels(rolls: list[dict[str, Any]]) -> dict[str, str]:
    """Map roll id to a unique display label."""
    labels = {roll["id"]: f"{roll['name']} - {roll['material']}" for roll in rolls}
    counts: dict[str, int] = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    return {
        roll_id: label if counts[label] == 1 else f"{label} ({roll_id})"
        for roll_id, label in labels.items()
    }


def models_using_roll(roll_id: str) -> list[str]:
    return [
        model["name"]
        for model in load()["models"]
        if any(piece["materialId"] == roll_id for piece in model["pieces"])
    ]


def models_using_hardware(hardware_id: str) -> list[str]:
    return [
        model["name"]
        for model in load()["models"]
        if any(use["hardwareId"] == hardware_id for use in model.get("hardwareItems") or [])
    ]


def import_draft(draft: dict[str, Any]) -> dict[str, int]:
    """Store what the AI assistant collected as catalog entries."""
    for roll in draft.get("rolls", []):
        upsert("rolls", roll)
    for item in draft.get("hardware", []):
        upsert("hardware", item)
    models = 0
    if draft.get("pieces"):
        name = draft.get("modelName") or "Model from assistant"
        upsert(
            "models",
            {
                "id": "asst-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "model"),
                "name": name,
                "description": "Created by the assistant",
                "pieces": draft["pieces"],
                "hardwareItems": draft.get("hardwareUses") or [],
            },
        )
        models = 1
    return {
        "rolls": len(draft.get("rolls", [])),
        "hardware": len(draft.get("hardware", [])),
        "models": models,
    }
