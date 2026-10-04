import hmac

import streamlit as st

from src.config import APP_PASSWORD


AUTH_SESSION_KEY = "sentinelrag_authenticated"


def require_authentication() -> bool:
    """
    Require a simple password before allowing access
    to the SentinelRAG application.
    """
    if not APP_PASSWORD:
        st.error(
            "APP_PASSWORD is not configured. "
            "Set it in .env or in the deployment secrets."
        )
        st.stop()

    if st.session_state.get(
        AUTH_SESSION_KEY,
        False,
    ):
        return True

    st.title("SentinelRAG")
    st.caption(
        "SOC Operations and Cybersecurity Incident Response"
    )

    with st.form(
        "sentinelrag_login",
        clear_on_submit=False,
    ):
        password = st.text_input(
            "Application password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Sign in",
            use_container_width=True,
        )

    if submitted:
        if hmac.compare_digest(
            password,
            APP_PASSWORD,
        ):
            st.session_state[
                AUTH_SESSION_KEY
            ] = True

            st.rerun()

        st.error("Invalid password.")

    return False


def render_logout_button() -> None:
    """
    Render a logout control in the sidebar.
    """
    if st.sidebar.button(
        "Log out",
        use_container_width=True,
    ):
        st.session_state.pop(
            AUTH_SESSION_KEY,
            None,
        )
        st.session_state.pop(
            "sentinelrag_last_result",
            None,
        )

        st.rerun()
