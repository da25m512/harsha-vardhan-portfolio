"""
Marothu Harsha Vardhan — Director
=================================
A two-role portfolio platform.

  * Public  — anyone, no login: read everything, leave a message.
  * Admin   — password protected at ?view=admin: edit every word,
              image and video on the site.

Content is stored in a GitHub repository (a separate `content` branch), so
nothing is lost when the app restarts and every change is version-history'd.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Marothu Harsha Vardhan — Director",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Portfolio of Marothu Harsha Vardhan, director."},
)

import hv_admin as admin
import hv_data as D
import hv_public as public  # noqa: E402
from hv_security import enforce_session_timeout, is_admin  # noqa: E402
from hv_theme import css  # noqa: E402


def main() -> None:
    try:
        content = D.load_content()
    except Exception:
        st.error("Couldn't load the site content. Retrying usually fixes it.", icon="⚠️")
        content = {
            "site": dict(D.DEFAULT_SITE),
            "projects": [], "timeline": [], "gallery": [], "press": [], "messages": [],
        }

    site = content["site"]
    st.markdown(
        css(site.get("accent", "#FF4A1C"), site.get("accent_2", "#F5B841"), bool(site.get("grain", True))),
        unsafe_allow_html=True,
    )

    enforce_session_timeout()
    view = (st.query_params.get("view") or "").lower()

    # Admin is reached only at ?view=admin. Staying logged in does not trap
    # the director inside the console -- "Public site" clears the parameter.
    if view == "admin":
        if admin.login_gate():
            admin.render(content)
        return

    public.render(content)
    label = "Admin console" if is_admin() else "Admin"
    st.markdown(
        '<div style="text-align:center;padding:0 0 26px;font-family:\'IBM Plex Mono\',monospace;'
        'font-size:9.5px;letter-spacing:.22em;text-transform:uppercase">'
        f'<a href="?view=admin" style="color:rgba(233,231,223,.24);text-decoration:none">{label}</a></div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
