"""?page=my · 마이페이지: the logged-in learner's status (same card as home) and every saved review record."""
import html

import streamlit as st

import accounts
from inspection import MODES
from ui import shell, fragment, footer, render_html

ALL = '전체'


def render():
    shell(None, no_chat=True, current='my')
    user = accounts.current_user()
    from home import status_card
    head = ('<main id="workspace" tabindex="-1" class="my-main"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 마이페이지</div>'
            '<section class="workspace-title my-title"><div class="title-main"><h1>마이페이지</h1>')
    if not user:
        fragment(head + '<p>로그인하면 내 학습 현황과 검토 기록을 볼 수 있습니다.</p></div></section></main>')
        fragment('<div class="my-band">' + status_card(on_mypage=True) + '</div>')
        fragment('<div class="ws-foot">' + footer() + '</div>')
        return
    info = accounts.user_info(user['id']) or {}
    meta = f"가입 {html.escape((info.get('created') or '')[:10])}" + (f" · 최근 로그인 {html.escape(info['last_login'][:16])}" if info.get('last_login') else '')
    fragment(head + f'<p><b>{html.escape(user["name"])}</b> 님 · {meta}</p></div>'
             '</section></main>')
    fragment('<div class="my-band">' + status_card(on_mypage=True) + '</div>')
    with st.container(border=True, key='t13my_records'):
        fragment('<div class="band-head my-rec-head"><h2 id="records">내 검토 기록</h2></div>')
        labels = [ALL] + [f"{c['number']}. {c['title']}" for c in MODES.values()]
        pick = st.segmented_control('검사 종류', labels, default=ALL, key='t13my_filter', label_visibility='collapsed')
        mode = None if pick in (None, ALL) else list(MODES)[labels.index(pick) - 1]
        from review import log_view
        log_view(user, 't13my', mode=mode)
    if st.query_params.get('view') == 'records':
        render_html('<span hidden></span>', "setTimeout(()=>document.querySelector('.st-key-t13my_records')?.scrollIntoView({behavior:'smooth',block:'start'}),600);")
    fragment('<div class="ws-foot">' + footer() + '</div>')
