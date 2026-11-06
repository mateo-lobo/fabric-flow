import uuid

import streamlit as st

import api_client
import catalog
from i18n import t
import render

st.session_state.setdefault("assistant_session", uuid.uuid4().hex)
st.session_state.setdefault("assistant_messages", [])
st.session_state.setdefault("assistant_draft", None)
st.session_state.setdefault("assistant_result", None)

SUGGESTIONS = {
    t("Tote bag"): t(
        "I want to calculate a tote bag. Canvas fabric, 140 cm wide, 50 m roll at R$ 20 per meter, rotation allowed."
    ),
    t("What do you need to know?"): t("What information do you need from me to calculate a bag?"),
}


def show(text: str) -> None:
    # Escape dollar signs so "R$" amounts are not rendered as math.
    st.markdown(text.replace("$", "\\$"))


def reset_conversation() -> None:
    st.session_state.assistant_session = uuid.uuid4().hex
    st.session_state.assistant_messages = []
    st.session_state.assistant_draft = None
    st.session_state.assistant_result = None


st.caption(t("Describe your bag in plain language. The assistant asks for what is missing and uses the calculator for every number."))
st.button(t("New conversation"), icon=":material/refresh:", on_click=reset_conversation)

messages = st.session_state.assistant_messages
for message in messages:
    with st.chat_message(message["role"]):
        show(message["content"])

prompt = st.chat_input(t("Describe your bag, fabric and batch size..."), submit_mode="disable")
if not prompt and not messages:
    chosen = st.pills(t("Try asking"), list(SUGGESTIONS), label_visibility="collapsed", key="assistant_pills")
    if chosen:
        prompt = SUGGESTIONS[chosen]

if prompt:
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        show(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner(t("Thinking...")):
                reply = api_client.chat(st.session_state.assistant_session, prompt)
        except api_client.ApiError as error:
            messages.pop()
            st.error(t(str(error)))
        else:
            show(reply["reply"])
            messages.append({"role": "assistant", "content": reply["reply"]})
            st.session_state.assistant_draft = reply["draft"]
            st.session_state.assistant_result = reply["result"]

draft = st.session_state.assistant_draft
if draft and (draft["rolls"] or draft["pieces"] or draft["hardware"]):
    with st.expander(t("What the assistant has collected"), expanded=False):
        st.json(draft, expanded=False)
    if draft["pieces"]:
        if st.button(t("Save to catalog"), icon=":material/save:"):
            counts = catalog.import_draft(draft)
            st.toast(
                t(
                    "Saved {rolls} rolls, {hardware} hardware items, {models} model.",
                    rolls=counts["rolls"],
                    hardware=counts["hardware"],
                    models=counts["models"],
                ),
                icon=":material/check:",
            )

if st.session_state.assistant_result:
    st.subheader(t("Latest result"))
    render.show_result(st.session_state.assistant_result, key="assistant")
