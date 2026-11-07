import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, '/data/hackathon/team13')
from inspection import render as render_inspection
from home import render as render_home

st.set_page_config(page_title='team13 | LNG 탱크 품질검사 교육',page_icon=str(Path(__file__).parent/'assets/brand/icon-64.png'),layout='wide',initial_sidebar_state='collapsed')
mode=st.query_params.get('inspection')
if mode is None:
    render_home()
else:
    render_inspection(mode)
