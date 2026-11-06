import pandas as pd
import streamlit as st

import catalog
from i18n import t

st.caption(t("Register and edit your fabric rolls."))


@st.dialog(t("Fabric roll"))
def roll_form(roll: dict) -> None:
    with st.form("roll_form", border=False):
        name = st.text_input(t("Roll name"), value=roll.get("name", ""))
        material = st.text_input(t("Material"), value=roll.get("material", ""))
        color = st.text_input(t("Color"), value=roll.get("color") or "")
        left, right = st.columns(2)
        width = left.number_input(
            t("Width (cm)"), min_value=1.0, max_value=500.0, value=float(roll.get("widthCm", 140)), step=1.0
        )
        length = right.number_input(
            t("Length (m)"), min_value=0.1, max_value=1000.0, value=float(roll.get("lengthM", 50)), step=1.0
        )
        price = left.number_input(
            t("Price per meter (R$)"), min_value=0.0, value=float(roll.get("pricePerMeter", 0)), step=0.5
        )
        batch = right.number_input(
            t("Cut batch length (m)"),
            min_value=1.0,
            max_value=50.0,
            value=float(roll.get("cutBatchLengthM") or 10.5),
            step=0.5,
        )
        rotation = st.checkbox(t("Allow rotation (90°)"), value=roll.get("allowsRotation", True))
        directional = st.checkbox(
            t("Directional pattern"),
            value=roll.get("hasDirectionalPattern", False),
            help=t("Pieces cannot be rotated on a directional pattern."),
        )
        submitted = st.form_submit_button(t("Save"), type="primary")
    if submitted:
        if not name.strip() or not material.strip():
            st.error(t("Name and material are required."))
            return
        catalog.upsert(
            "rolls",
            {
                "id": roll.get("id"),
                "name": name.strip(),
                "material": material.strip(),
                "color": color.strip() or None,
                "widthCm": width,
                "lengthM": length,
                "pricePerMeter": price,
                "cutBatchLengthM": batch,
                "allowsRotation": rotation,
                "hasDirectionalPattern": directional,
            },
        )
        st.rerun()


@st.dialog(t("Delete roll"))
def confirm_delete(roll: dict) -> None:
    used_by = catalog.models_using_roll(roll["id"])
    if used_by:
        st.error(t("This roll is used by: {names}. Remove it from those models first.", names=", ".join(used_by)))
        return
    st.write(t("Delete **{name}**? This cannot be undone.", name=roll["name"]))
    if st.button(t("Delete"), type="primary"):
        catalog.delete("rolls", roll["id"])
        st.rerun()


rolls = catalog.load()["rolls"]
selected = None
if rolls:
    table = pd.DataFrame(
        [
            {
                t("Name"): roll["name"],
                t("Material"): roll["material"],
                t("Color"): roll.get("color") or "",
                t("Width (cm)"): roll["widthCm"],
                t("Length (m)"): roll["lengthM"],
                t("Price per meter"): roll["pricePerMeter"],
                t("Rotation"): roll.get("allowsRotation", True),
                t("Directional"): roll.get("hasDirectionalPattern", False),
            }
            for roll in rolls
        ]
    )
    event = st.dataframe(
        table,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="rolls_table",
        column_config={
            t("Price per meter"): st.column_config.NumberColumn(format="R$ %.2f"),
            t("Rotation"): st.column_config.CheckboxColumn(),
            t("Directional"): st.column_config.CheckboxColumn(),
        },
    )
    if event.selection.rows:
        selected = rolls[event.selection.rows[0]]
else:
    st.info(t("No rolls registered yet."))

actions = st.container(horizontal=True)
if actions.button(t("New roll"), icon=":material/add:", type="primary"):
    roll_form({})
if actions.button(t("Edit"), icon=":material/edit:", disabled=selected is None):
    roll_form(selected)
if actions.button(t("Delete"), icon=":material/delete:", disabled=selected is None):
    confirm_delete(selected)
