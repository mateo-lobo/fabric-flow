import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage

from ..models import BagModel, CalculationRequest, Hardware, HardwareUse, Piece, Roll


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


@dataclass
class Session:
    """Draft inputs collected during one conversation."""

    model_name: str = "Modelo sem nome"
    batch_size: float | None = None
    rolls: dict[str, Roll] = field(default_factory=dict)
    hardware: dict[str, Hardware] = field(default_factory=dict)
    hardware_uses: list[HardwareUse] = field(default_factory=list)
    pieces: list[Piece] = field(default_factory=list)
    messages: list[BaseMessage] = field(default_factory=list)
    last_result: dict[str, Any] | None = None
    last_optimization: dict[str, Any] | None = None

    def build_request(self) -> CalculationRequest:
        """Raises pydantic.ValidationError while the draft is incomplete."""
        return CalculationRequest(
            model=BagModel(
                id=slugify(self.model_name),
                name=self.model_name,
                pieces=self.pieces,
                hardwareItems=self.hardware_uses or None,
            ),
            rolls=list(self.rolls.values()),
            hardware=list(self.hardware.values()),
            batchSize=self.batch_size or 0,
        )

    def draft(self) -> dict[str, Any]:
        return {
            "modelName": self.model_name,
            "batchSize": self.batch_size,
            "rolls": [roll.model_dump(by_alias=True) for roll in self.rolls.values()],
            "hardware": [item.model_dump(by_alias=True) for item in self.hardware.values()],
            "hardwareUses": [use.model_dump(by_alias=True) for use in self.hardware_uses],
            "pieces": [piece.model_dump(by_alias=True, exclude_none=True) for piece in self.pieces],
        }


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str) -> Session:
        return self._sessions.setdefault(session_id, Session())

    def clear(self) -> None:
        self._sessions.clear()


store = SessionStore()
