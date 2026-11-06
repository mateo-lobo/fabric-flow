"""Build and describe pattern pieces in the shape the calculation API expects."""

from typing import Any

from catalog import new_id
from i18n import t

GEOMETRIES = {
    "rectangle": "Rectangle",
    "circle": "Circle",
    "triangle": "Triangle",
    "trapezoid": "Trapezoid",
}


def build_piece(
    geometry: str,
    name: str,
    roll_id: str,
    quantity: float,
    **dims: float,
) -> dict[str, Any]:
    """Raises ValueError with a user-facing message when the input is unusable."""
    if not name.strip():
        raise ValueError("Piece name is required.")
    piece: dict[str, Any] = {
        "id": new_id(),
        "name": name.strip(),
        "geometry": geometry,
        "quantity": quantity,
        "materialId": roll_id,
    }
    if geometry == "rectangle":
        piece.update(widthCm=dims["width"], heightCm=dims["height"])
    elif geometry == "circle":
        piece.update(radiusCm=dims["radius"], widthCm=dims["radius"] * 2, heightCm=dims["radius"] * 2)
    elif geometry == "triangle":
        piece.update(baseCm=dims["base"], widthCm=dims["base"], heightCm=dims["height"])
    elif geometry == "trapezoid":
        if dims["base2"] < dims["base1"]:
            raise ValueError("The larger base cannot be smaller than the smaller base.")
        piece.update(
            base1Cm=dims["base1"],
            base2Cm=dims["base2"],
            widthCm=dims["base1"],
            heightCm=dims["height"],
        )
    else:
        raise ValueError(f"Unknown shape: {geometry}")
    return piece


def describe(piece: dict[str, Any]) -> str:
    shape = GEOMETRIES.get(piece.get("geometry", "rectangle"), "Rectangle")
    geometry = piece.get("geometry", "rectangle")
    if geometry == "circle":
        size = f"radius {piece.get('radiusCm', piece['widthCm'] / 2):g} cm"
    elif geometry == "triangle":
        size = f"base {piece.get('baseCm', piece['widthCm']):g} x height {piece['heightCm']:g} cm"
    elif geometry == "trapezoid":
        base1 = piece.get("base1Cm", piece["widthCm"])
        base2 = piece.get("base2Cm", piece["widthCm"] * 1.5)
        size = f"bases {base1:g}/{base2:g} x height {piece['heightCm']:g} cm"
    else:
        size = f"{piece['widthCm']:g} x {piece['heightCm']:g} cm"
    return t(
        "{name} - {shape}, {size}, {quantity:g} per bag",
        name=piece["name"],
        shape=t(shape),
        size=size,
        quantity=piece["quantity"],
    )
