from datetime import datetime

import pandas as pd
import streamlit as st

import api_client
import catalog
from i18n import t
import render

data = catalog.load()
models = {model["id"]: model for model in data["models"]}

if not models:
    st.info(t("Create a bag model first (Catalog > Bag models), or describe it to the assistant."))
    st.stop()

with st.container(border=True):
    st.subheader(t("Calculation setup"))
    left, right = st.columns([3, 1])
    model_id = left.selectbox(
        t("Bag model"), list(models), format_func=lambda item: models[item]["name"], key="calc_model"
    )
    batch_size = right.number_input(
        t("Batch size (bags)"), min_value=1, value=100, step=10, key="calc_batch"
    )
    run = st.button(t("Calculate"), type="primary", icon=":material/calculate:")

if run:
    try:
        with st.spinner(t("Calculating...")):
            outcome = api_client.calculate(models[model_id], data["rolls"], data["hardware"], batch_size)
    except api_client.ApiError as error:
        st.session_state.calc = None
        st.error(t(str(error)))
    else:
        st.session_state.calc = {**outcome, "applied": None, "historyId": None}

calc = st.session_state.get("calc")
if not calc:
    st.stop()

render.show_result(calc["result"], key="calculator")

scenarios = calc["optimization"]["scenarios"]
if scenarios:
    st.subheader(t("Scrap reuse opportunities"))
    st.caption(
        t(
            "{count} scenarios found. Pick one to cut extra pieces from fabric that would otherwise be wasted; "
            "the total cost is reduced by the fabric you reuse.",
            count=len(scenarios),
        )
    )
    table = pd.DataFrame(
        [
            {
                t("Fit piece"): scenario["pieceName"],
                t("Into scrap from"): scenario["wastePieceName"],
                t("Pieces fitted"): scenario["piecesFitted"],
                t("Scrap efficiency (%)"): scenario["efficiency"],
                t("Remaining waste (cm²)"): scenario["remainingWasteAreaCm2"],
            }
            for scenario in scenarios
        ]
    )
    event = st.dataframe(
        table,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="scenario_table",
        column_config={
            t("Scrap efficiency (%)"): st.column_config.NumberColumn(format="%.1f"),
            t("Remaining waste (cm²)"): st.column_config.NumberColumn(format="%.0f"),
        },
    )
    chosen = scenarios[event.selection.rows[0]] if event.selection.rows else None
    if calc["applied"]:
        st.success(t("A scrap scenario is already applied to this calculation."), icon=":material/check:")
    elif st.button(t("Apply selected scenario"), icon=":material/recycling:", disabled=chosen is None):
        try:
            calc["result"] = api_client.apply_scenario(calc, chosen)
        except api_client.ApiError as error:
            st.error(t(str(error)))
        else:
            calc["applied"] = chosen["id"]
            st.rerun()

st.subheader(t("Save calculation"))
default_name = t(
    "{model} - {batch:g} units - {date}",
    model=calc["result"]["modelName"],
    batch=calc["result"]["batchSize"],
    date=datetime.now().strftime("%Y-%m-%d"),
)
with st.container(horizontal=True):
    scenario_name = st.text_input(t("Name"), value=default_name, key="calc_save_name")
    save = st.button(t("Save to history"), icon=":material/save:")
if save:
    if not scenario_name.strip():
        st.error(t("Give the calculation a name."))
    else:
        saved = catalog.upsert(
            "history",
            {
                "id": calc["historyId"],
                "name": scenario_name.strip(),
                "modelId": model_id,
                "modelName": calc["result"]["modelName"],
                "batchSize": calc["result"]["batchSize"],
                "savedAt": datetime.now().isoformat(timespec="seconds"),
                "result": calc["result"],
            },
        )
        calc["historyId"] = saved["id"]
        st.toast(t("Calculation saved"), icon=":material/check:")
