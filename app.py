"""Entry point for `streamlit run app.py`.

Started by `streamlit run`, this file defines `app` (an st.App) that serves the page script main.py plus the
chatbot relay routes from chat_api.py under server.baseUrlPath. If an older server process executes this file as
a page script instead, it simply runs main.py so the site keeps working.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from streamlit.runtime.scriptrunner import get_script_run_ctx

if get_script_run_ctx() is not None:  # executed as a page script (no st.App): just render the site
    import runpy
    runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
else:
    import streamlit as st
    from chat_api import routes
    app = st.App(str(ROOT / 'main.py'), routes=routes(st.config.get_option('server.baseUrlPath')))
