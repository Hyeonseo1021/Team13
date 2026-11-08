import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, '/data/hackathon/team13')
from inspection import render as render_inspection
from home import render as render_home

st.set_page_config(page_title='LNG 탱크 품질 검사 교육 플랫폼 | team13',page_icon=str(Path(__file__).parent/'assets/brand/icon-64.png'),layout='wide',initial_sidebar_state='collapsed')
mode=st.query_params.get('inspection')
if st.query_params.get('page')=='login':
    from login import render as render_login
    render_login()
elif st.query_params.get('page')=='judge' or (mode and st.query_params.get('task')=='review'):
    from judge_page import render as render_judge  # old ?inspection=..&task=review links land here too
    render_judge(mode or 'classification')
elif st.query_params.get('page')=='exam':
    from exam_page import render as render_exam
    render_exam()
elif st.query_params.get('page')=='guide':
    from guide_page import render as render_guide
    render_guide()
elif st.query_params.get('page')=='classes':
    from classes_page import render as render_classes
    render_classes()
elif st.query_params.get('page')=='privacy':
    from privacy_page import render as render_privacy
    render_privacy()
elif st.query_params.get('page')=='my':
    from mypage import render as render_mypage
    render_mypage()
elif mode is None:
    render_home()
else:
    render_inspection(mode)
