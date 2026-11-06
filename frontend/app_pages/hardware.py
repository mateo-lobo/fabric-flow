import pandas as pd
import streamlit as st

import catalog
from i18n import t

st.caption(t("Register the hardware (zippers, buckles, rings...) used in your bags."))


@st.dialog(t("Hardware item"))
def hardware_form(item: dict) -> None:
    with st.form("hardware_form", border=False):
        name = st.text_input(t("Name"), value=item.get("name", ""))
        left, right = st.columns(2)
        price = left.number_input(
            t("Price per unit (R$)"), min_value=0.0, value=float(item.get("pricePerUnit", 0)), step=0.1
        )
        quantity = right.number_input(
            t("Default quantity per bag"),
            min_value=0.0,
            value=float(item.get("quantityPerProduct", 1)),
            step=1.0,
        )
        submitted = st.form_submit_button(t("Save"), type="primary")
    if submitted:
        if not name.strip():
            st.error(t("Name is required."))
            return
        catalog.upsert(
            "hardware",
            {
                "id": item.get("id"),
                "name": name.strip(),
                "pricePerUnit": price,
                "quantityPerProduct": quantity,
            },
        )
        st.rerun()


@st.dialog(t("Delete hardware"))
def confirm_delete(item: dict) -> None:
    used_by = catalog.models_using_hardware(item["id"])
    if used_by:
        st.error(t("This item is used by: {names}. Remove it from those models first.", names=", ".join(used_by)))
        return
    st.write(t("Delete **{name}**? This cannot be undone.", name=item["name"]))
    if st.button(t("Delete"), type="primary"):
        catalog.delete("hardware", item["id"])
        st.rerun()


items = catalog.load()["hardware"]
selected = None
if items:
    table = pd.DataFrame(
        [
            {
                t("Name"): item["name"],
                t("Price per unit"): item["pricePerUnit"],
                t("Default quantity per bag"): item.get("quantityPerProduct", 1),
            }
            for item in items
        ]
    )
    event = st.dataframe(
        table,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="hardware_table",
        column_config={t("Price per unit"): st.column_config.NumberColumn(format="R$ %.2f")},
    )
    if event.selection.rows:
        selected = items[event.selection.rows[0]]
else:
    st.info(t("No hardware registered yet."))

actions = st.container(horizontal=True)
if actions.button(t("New item"), icon=":material/add:", type="primary"):
    hardware_form({})
if actions.button(t("Edit"), icon=":material/edit:", disabled=selected is None):
    hardware_form(selected)
if actions.button(t("Delete"), icon=":material/delete:", disabled=selected is None):
    confirm_delete(selected)
