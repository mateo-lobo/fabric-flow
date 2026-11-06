import pandas as pd
import streamlit as st

import catalog
from i18n import t
import render

data = catalog.load()
history = sorted(data["history"], key=lambda entry: entry["savedAt"], reverse=True)

st.caption(t("BAG PRODUCTION / MATERIAL PLANNING"))
st.header(t("From fabric roll to cut plan"))
st.write(t("Manage fabric usage, cutting efficiency and cost in one guided flow."))
if st.button(t("Start a calculation"), type="primary", icon=":material/calculate:"):
    st.switch_page("app_pages/calculator.py")

st.subheader(t("Your workflow"))
steps = [
    ("1. Add fabric rolls", "Register width, length, price per meter, rotation and directional-print rules."),
    (
        "2. Define bag pieces",
        "Create a bag model, enter each piece's shape and dimensions, quantity per bag, and fabric roll. Add hardware if needed.",
    ),
    (
        "3. Calculate a production batch",
        "Choose a bag model and batch size. Review fabric consumption, roll count, cost and cutting efficiency.",
    ),
    (
        "4. Review and save",
        "Check scrap reuse options, apply a scenario if useful, and save the calculation or export cut details as CSV.",
    ),
]
columns = st.columns(4)
for column, (heading, description) in zip(columns, steps):
    with column:
        st.markdown(f"#### {t(heading)}")
        st.write(t(description))

with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown(f"**{t('Need a hand?')}**")
    st.write(t("Describe the bag, fabric and batch in everyday language. The assistant will ask for missing details."))
    if st.button(t("Open assistant"), icon=":material/chat:"):
        st.switch_page("app_pages/assistant.py")

counts = st.container(horizontal=True)
counts.metric(t("Bag models"), len(data["models"]), border=True, width="content")
counts.metric(t("Fabric rolls"), len(data["rolls"]), border=True, width="content")
counts.metric(t("Hardware items"), len(data["hardware"]), border=True, width="content")
counts.metric(t("Saved calculations"), len(history), border=True, width="content")

st.subheader(t("Recent calculations"))
if not history:
    st.caption(t("No calculations saved yet."))
else:
    recent = history[:8]
    table = pd.DataFrame(
        [
            {
                t("Name"): entry["name"],
                t("Batch"): entry["batchSize"],
                t("Total cost"): entry["result"]["totalCost"],
                t("Efficiency (%)"): entry["result"]["averageEfficiency"],
                t("Saved at"): entry["savedAt"],
            }
            for entry in recent
        ]
    )
    average = sum(entry["result"]["averageEfficiency"] for entry in history) / len(history)
    st.caption(t("Average efficiency across all saved calculations: {value:.1f}%", value=average))
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            t("Total cost"): render.BRL,
            t("Efficiency (%)"): st.column_config.NumberColumn(format="%.1f"),
            t("Batch"): st.column_config.NumberColumn(format="%g"),
        },
    )
    st.bar_chart(
        table,
        x=t("Name"),
        y=t("Total cost"),
        y_label=f"{t('Total cost')} (R$)",
        x_label=t("Calculation"),
    )
