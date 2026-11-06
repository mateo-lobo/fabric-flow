import copy

import pandas as pd
import streamlit as st

import catalog
from pieces import GEOMETRIES, build_piece, describe
from i18n import t

st.session_state.setdefault("editing_model", None)


def start_editing(model: dict | None) -> None:
    draft = copy.deepcopy(model) if model else {"name": "", "description": "", "pieces": [], "hardwareItems": []}
    draft["_key"] = catalog.new_id()
    draft["_n"] = 0
    st.session_state.editing_model = draft


def stop_editing() -> None:
    st.session_state.editing_model = None


def remove_piece(index: int) -> None:
    st.session_state.editing_model["pieces"].pop(index)


@st.dialog(t("Delete model"))
def confirm_delete(model: dict) -> None:
    st.write(t("Delete **{name}**? Saved calculations are kept.", name=model["name"]))
    if st.button(t("Delete"), type="primary"):
        catalog.delete("models", model["id"])
        st.rerun()


editing = st.session_state.editing_model

if editing is None:
    st.caption(t("A bag model is a list of pieces, the roll each piece is cut from, and its hardware."))
    models = catalog.load()["models"]
    selected = None
    if models:
        table = pd.DataFrame(
            [
                {
                    t("Name"): model["name"],
                    t("Description"): model.get("description", ""),
                    t("Pieces"): len(model["pieces"]),
                    t("Hardware items"): len(model.get("hardwareItems") or []),
                }
                for model in models
            ]
        )
        event = st.dataframe(
            table,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="models_table",
        )
        if event.selection.rows:
            selected = models[event.selection.rows[0]]
    else:
        st.info(t("No bag models yet. Create one, or describe it to the assistant."))

    actions = st.container(horizontal=True)
    actions.button(t("New model"), icon=":material/add:", type="primary", on_click=start_editing, args=(None,))
    actions.button(
        t("Edit"), icon=":material/edit:", disabled=selected is None, on_click=start_editing, args=(selected,)
    )
    if actions.button(t("Delete"), icon=":material/delete:", disabled=selected is None):
        confirm_delete(selected)
else:
    key = editing["_key"]
    step = editing["_n"]
    data = catalog.load()
    rolls, hardware = data["rolls"], data["hardware"]
    roll_names = catalog.roll_labels(rolls)

    with st.container(border=True):
        name = st.text_input(t("Model name"), value=editing["name"], key=f"model_name_{key}")
        description = st.text_area(
            t("Description (optional)"), value=editing.get("description", ""), key=f"model_desc_{key}"
        )

    with st.container(border=True):
        st.subheader(t("Pieces"))
        if not editing["pieces"]:
            st.caption(t("No pieces yet."))
        for index, piece in enumerate(editing["pieces"]):
            row = st.container(horizontal=True)
            roll_label = roll_names.get(piece["materialId"], t("roll no longer exists"))
            row.markdown(f"{describe(piece)}  \n:gray[{roll_label}]")
            row.button(
                t("Remove"),
                icon=":material/delete:",
                key=f"remove_{key}_{index}_{len(editing['pieces'])}",
                on_click=remove_piece,
                args=(index,),
            )

        st.divider()
        st.markdown(f"**{t('Add a piece')}**")
        if not rolls:
            st.warning(t("Register a fabric roll first (Catalog > Fabric rolls)."))
        else:
            wkey = f"{key}_{step}"
            geometry = st.selectbox(
                t("Shape"), list(GEOMETRIES), format_func=lambda shape: t(GEOMETRIES[shape]), key=f"shape_{wkey}"
            )
            piece_name = st.text_input(t("Piece name"), key=f"piece_name_{wkey}")
            left, right = st.columns(2)
            roll_id = left.selectbox(
                t("Cut from roll"), list(roll_names), format_func=roll_names.get, key=f"piece_roll_{wkey}"
            )
            quantity = right.number_input(
                t("Quantity per bag"), min_value=1, value=1, step=1, key=f"piece_qty_{wkey}"
            )
            dims: dict[str, float] = {}
            fields = {
                "rectangle": [("width", t("Width (cm)")), ("height", t("Height (cm)"))],
                "circle": [("radius", t("Radius (cm)"))],
                "triangle": [("base", t("Base (cm)")), ("height", t("Height (cm)"))],
                "trapezoid": [
                    ("base1", t("Smaller base (cm)")),
                    ("base2", t("Larger base (cm)")),
                    ("height", t("Height (cm)")),
                ],
            }[geometry]
            for column, (field, label) in zip(st.columns(len(fields)), fields):
                dims[field] = column.number_input(
                    label, min_value=0.1, value=10.0, step=1.0, key=f"dim_{field}_{wkey}"
                )
            if st.button(t("Add piece"), icon=":material/add:", key=f"add_piece_{wkey}"):
                try:
                    editing["pieces"].append(build_piece(geometry, piece_name, roll_id, quantity, **dims))
                except ValueError as error:
                    st.error(t(str(error)))
                else:
                    editing["_n"] += 1
                    st.rerun()

    with st.container(border=True):
        st.subheader(t("Hardware"))
        hardware_names = {item["id"]: item["name"] for item in hardware}
        defaults = {item["id"]: item.get("quantityPerProduct", 1) for item in hardware}
        current = {
            use["hardwareId"]: use["quantity"]
            for use in editing.get("hardwareItems") or []
            if use["hardwareId"] in hardware_names
        }
        if not hardware:
            st.caption(t("No hardware registered (Catalog > Hardware)."))
        chosen = st.multiselect(
            t("Hardware items"),
            list(hardware_names),
            default=list(current),
            format_func=hardware_names.get,
            key=f"model_hw_{key}",
        )
        quantities = {
            hardware_id: st.number_input(
                t("{name} per bag", name=hardware_names[hardware_id]),
                min_value=0.0,
                value=float(current.get(hardware_id, defaults[hardware_id])),
                step=1.0,
                key=f"model_hwq_{key}_{hardware_id}",
            )
            for hardware_id in chosen
        }

    actions = st.container(horizontal=True)
    if actions.button(t("Save model"), icon=":material/save:", type="primary"):
        if not name.strip():
            st.error(t("Model name is required."))
        elif not editing["pieces"]:
            st.error(t("Add at least one piece."))
        else:
            catalog.upsert(
                "models",
                {
                    "id": editing.get("id"),
                    "name": name.strip(),
                    "description": description.strip(),
                    "pieces": editing["pieces"],
                    "hardwareItems": [
                        {"hardwareId": hardware_id, "quantity": quantity}
                        for hardware_id, quantity in quantities.items()
                    ],
                },
            )
            stop_editing()
            st.rerun()
    actions.button(t("Cancel"), on_click=stop_editing)
