import pandas as pd
import streamlit as st

import catalog
import render
from i18n import t

st.caption(t("Saved calculations you made in the calculator."))


@st.dialog(t("Delete calculation"))
def confirm_delete(entry: dict) -> None:
    st.write(t("Delete **{name}**? This cannot be undone.", name=entry["name"]))
    if st.button(t("Delete"), type="primary"):
        catalog.delete("history", entry["id"])
        st.rerun()


history = sorted(catalog.load()["history"], key=lambda entry: entry["savedAt"], reverse=True)
if not history:
    st.info(t("No saved calculations yet. Run a calculation and save it."))
    st.stop()

table = pd.DataFrame(
    [
        {
            t("Name"): entry["name"],
            t("Model"): entry["modelName"],
            t("Batch"): entry["batchSize"],
            t("Total cost"): entry["result"]["totalCost"],
            t("Efficiency (%)"): entry["result"]["averageEfficiency"],
            t("Saved at"): entry["savedAt"],
        }
        for entry in history
    ]
)
event = st.dataframe(
    table,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="history_table",
    column_config={
        t("Total cost"): render.BRL,
        t("Efficiency (%)"): st.column_config.NumberColumn(format="%.1f"),
        t("Batch"): st.column_config.NumberColumn(format="%g"),
    },
)
selected = history[event.selection.rows[0]] if event.selection.rows else None

if st.button(t("Delete"), icon=":material/delete:", disabled=selected is None):
    confirm_delete(selected)

if selected:
    st.divider()
    st.subheader(selected["name"])
    render.show_result(selected["result"], key="history")
else:
    st.caption(t("Select a row to see the full result."))
