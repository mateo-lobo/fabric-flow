import streamlit as st

import api_client
from i18n import t

st.set_page_config(page_title="FabricFlow", page_icon=":material/content_cut:", layout="wide")
st.session_state.setdefault("language", "English")


@st.cache_data(ttl=5)
def api_is_up() -> bool:
    return api_client.is_up()


page = st.navigation(
    {
        "": [
            st.Page("app_pages/dashboard.py", title=t("App guide"), icon=":material/home:", default=True),
            st.Page(
                "app_pages/calculator.py",
                title=t("Consumption calculator"),
                icon=":material/calculate:",
            ),
        ],
        t("Production"): [
            st.Page("app_pages/assistant.py", title=t("Assistant"), icon=":material/chat:"),
        ],
        t("Catalog"): [
            st.Page("app_pages/models.py", title=t("Bag models"), icon=":material/shopping_bag:"),
            st.Page("app_pages/rolls.py", title=t("Fabric rolls"), icon=":material/texture:"),
            st.Page("app_pages/hardware.py", title=t("Hardware"), icon=":material/hardware:"),
        ],
        t("Records"): [
            st.Page("app_pages/history.py", title=t("Calculation history"), icon=":material/history:"),
        ],
    }
)

with st.sidebar:
    st.segmented_control(
        t("Language"),
        ["English", "Português"],
        key="language",
    )
    st.page_link(
        "app_pages/calculator.py",
        label=t("Start a calculation"),
        icon=":material/calculate:",
    )
    if not api_is_up():
        st.error(t("Calculation API is offline"), icon=":material/error:")
        st.caption(t("Expected at {url}", url=api_client.base_url()))

st.title(page.title)
page.run()
