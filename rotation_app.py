"""Standalone theme rotation page (?view=rotation)."""
import streamlit as st
from startup_imports import import_local


def main():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    st.set_page_config(page_title='Theme Rotation | Crescent Trade Terminal — BETA',
        page_icon='🌙',layout='wide',initial_sidebar_state='collapsed')
    view=import_local('terminal_view')
    st.markdown(view.CSS,unsafe_allow_html=True)
    st.markdown(view.header(active='rotation',source='Yahoo Finance · completed daily candles'),unsafe_allow_html=True)
    liquid=import_local('liquid_app')
    import_local('rotation_view').render_rotation_page(liquid.daily_batch,datetime.now(ZoneInfo('America/New_York')))
