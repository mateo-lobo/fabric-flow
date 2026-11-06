"""Shared result display used by the calculator, assistant and history pages."""

from typing import Any

import pandas as pd
import streamlit as st

from i18n import language, t

BRL = st.column_config.NumberColumn(format="R$ %.2f")


def money(value: float) -> str:
    formatted = f"{value:,.2f}"
    if language() == "Português":
        formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def result_tables(result: dict[str, Any]) -> dict[str, pd.DataFrame]:
    tables = {
        "materials": pd.DataFrame(
            [
                {
                    t("Material"): item["materialName"],
                    t("Rolls"): item["rollsNeeded"],
                    t("Length (m)"): item["totalLengthM"],
                    t("Cofactor (m/unit)"): item["cofactor"],
                    t("Cost per unit"): item["costPerUnit"],
                    t("Total cost"): item["totalCost"],
                }
                for item in result["materialConsumption"]
            ]
        ),
        "cuts": pd.DataFrame(
            [
                {
                    t("Piece"): item["pieceName"],
                    t("Orientation"): t("Rotated 90°") if item["orientation"] == "rotated" else t("Normal"),
                    t("Pieces per roll"): item["totalPiecesPerRoll"],
                    t("Consumption per piece (m)"): item["consumptionMPerPiece"],
                    t("Efficiency (%)"): item["efficiency"],
                    t("Waste (cm²)"): item["wasteAreaCm2"],
                }
                for item in result["cutResults"]
            ]
        ),
        "hardware": pd.DataFrame(
            [
                {
                    t("Item"): item["hardwareName"],
                    t("Total quantity"): item["totalQuantity"],
                    t("Cost per unit"): item["costPerUnit"],
                    t("Total cost"): item["totalCost"],
                }
                for item in result.get("hardwareConsumption", [])
            ]
        ),
    }
    return tables


def show_result(result: dict[str, Any], key: str) -> None:
    tables = result_tables(result)
    batch = result["batchSize"]
    hardware_cost = result.get("totalHardwareCost", 0.0)
    total = result["totalCost"]

    metrics = st.container(horizontal=True)
    metrics.metric(t("Total cost"), money(total), border=True, width="content")
    metrics.metric(t("Cost per bag"), money(total / batch), border=True, width="content")
    metrics.metric(
        t("Average efficiency"), f"{result['averageEfficiency']:.1f}%", border=True, width="content"
    )
    metrics.metric(
        t("Total waste"), f"{result['totalWasteArea']:,.0f} cm²", border=True, width="content"
    )
    if hardware_cost:
        st.caption(
            t(
                "Fabric {fabric} + hardware {hardware} for {batch:g} bags",
                fabric=money(total - hardware_cost),
                hardware=money(hardware_cost),
                batch=batch,
            )
        )

    st.subheader(t("Consumption by material"))
    st.dataframe(
        tables["materials"],
        hide_index=True,
        column_config={
            t("Length (m)"): st.column_config.NumberColumn(format="%.2f"),
            t("Cofactor (m/unit)"): st.column_config.NumberColumn(format="%.4f"),
            t("Cost per unit"): BRL,
            t("Total cost"): BRL,
        },
    )

    st.subheader(t("Cut details"))
    st.dataframe(
        tables["cuts"],
        hide_index=True,
        column_config={
            t("Consumption per piece (m)"): st.column_config.NumberColumn(format="%.4f"),
            t("Efficiency (%)"): st.column_config.ProgressColumn(
                format="%.1f", min_value=0, max_value=100
            ),
            t("Waste (cm²)"): st.column_config.NumberColumn(format="%.0f"),
        },
    )
    st.download_button(
        t("Download cuts as CSV"),
        tables["cuts"].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"calculo_{result['modelName']}_{batch:g}un.csv",
        mime="text/csv",
        icon=":material/download:",
        key=f"download_{key}",
    )

    if not tables["hardware"].empty:
        st.subheader(t("Hardware consumption"))
        st.dataframe(
            tables["hardware"],
            hide_index=True,
            column_config={t("Cost per unit"): BRL, t("Total cost"): BRL},
        )
