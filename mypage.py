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
    if accounts.is_admin(user):
        admin_requests(user)
        from knowledge_ui import admin_panel
        admin_panel(user)
    exam_records(user)
    with st.container(border=True, key='t13my_records'):
        fragment('<div class="band-head my-rec-head"><h2 id="records">내 검토 기록</h2></div>')
        labels = [ALL] + [f"{c['number']}. {c['title']}" for c in MODES.values()]
        pick = st.segmented_control('검사 종류', labels, default=ALL, key='t13my_filter', label_visibility='collapsed')
        mode = None if pick in (None, ALL) else list(MODES)[labels.index(pick) - 1]
        from review import log_view
        log_view(user, 't13my', mode=mode, requests=True)
    target = {'records': 't13my_records', 'exams': 't13my_exams'}.get(st.query_params.get('view'))
    if target:
        render_html('<span hidden></span>', "setTimeout(()=>document.querySelector('.st-key-%s')?.scrollIntoView({behavior:'smooth',block:'start'}),600);" % target)
    fragment('<div class="ws-foot">' + footer() + '</div>')


def exam_records(user):
    """내 시험 기록: every 수행능력 평가 result, newest first."""
    from exam_page import fmt_time
    rows = accounts.exams_for(user['id'])
    with st.container(border=True, key='t13my_exams'):
        fragment('<div class="band-head my-rec-head"><h2 id="exams">내 시험 기록</h2><a class="band-more" href="?page=exam">역량평가 응시하기 <span aria-hidden="true">›</span></a></div>')
        if not rows:
            st.info('아직 응시한 시험이 없습니다. 메뉴의 역량평가 › 수행능력 평가에서 응시할 수 있습니다.')
            return
        best = max(round(r['score'] * 100 / r['total']) for r in rows if r['total'])
        st.caption(f"응시 {len(rows)}회 · 합격 {sum(r['passed'] for r in rows)}회 · 최고 {best}점")
        table = []
        for r in rows:
            d = r['detail']
            per = ' · '.join(f"{c['number']}번 {sum(x['ok'] for x in d if x['mode'] == m)}/{sum(x['mode'] == m for x in d)}"
                             for m, c in MODES.items() if any(x['mode'] == m for x in d))
            table.append({'응시 시각': r['created'][:16], '점수': f"{r['score']}/{r['total']} ({round(r['score'] * 100 / r['total']) if r['total'] else 0}점)",
                          '결과': '합격' if r['passed'] else '불합격', '검사별 정답': per, '소요 시간': fmt_time(r['seconds'])})
        st.dataframe(table, hide_index=True, width='stretch', key='t13my_exam_table')


def admin_requests(admin):
    """관리자: 학습자가 올린 시험 문제 승인신청을 사진과 함께 보고 승인(정답 정정 가능)·반려한다."""
    if not accounts.is_admin(admin):  # admin account only (also enforced in accounts.decide_exam_request)
        return
    from inspection import case_thumb
    waiting = accounts.exam_requests(status=accounts.REQ_WAIT)
    approved = accounts.exam_requests(status=accounts.REQ_OK)
    with st.container(border=True, key='t13my_examreq'):
        fragment('<div class="band-head my-rec-head"><h2 id="examreq">시험 문제 승인 관리</h2></div>')
        per = ' · '.join(f"{c['number']}번 {sum(r['mode'] == m for r in approved)}개" for m, c in MODES.items())
        st.caption(f'승인 대기 {len(waiting)}건 · 출제 중인 추가 문제 {len(approved)}개 ({per}) · 승인한 사진은 수행능력 평가에 기본 문제와 섞여 출제됩니다.')
        msg = st.session_state.pop('t13req_msg', None)
        if msg: st.success(msg)
        if not waiting:
            st.info('승인 대기 중인 신청이 없습니다.')
        for r in waiting:
            path = accounts.pool_file(r['photo'])
            with st.container(border=True, key=f"t13reqrow_{r['id']}"):
                img, info, act = st.columns([1, 2.2, 1.6], gap='small', vertical_alignment='center')
                if path:
                    img.image(case_thumb(str(path), path.stat().st_mtime, r['mode'], 480), width='stretch')
                info.markdown(f"**{html.escape(MODES.get(r['mode'], {}).get('title', r['mode']))}** · 신청자 {html.escape(r['requester'])}  \n"
                              f"신청 정답: **{'불량' if r['defect'] else '양품'}** ({html.escape(r['label'])})  \n"
                              f":gray[{html.escape(r['file'])} · {r['created'][:16]}]")
                ans = act.segmented_control('정답', ['양품', '불량'], default='불량' if r['defect'] else '양품',
                                            key=f"t13req_ans_{r['id']}", width='stretch')
                y, n = act.columns(2)
                if y.button('승인', type='primary', key=f"t13req_ok_{r['id']}", width='stretch', disabled=ans is None):
                    accounts.decide_exam_request(admin, r['id'], True, defect=ans == '불량')
                    st.session_state['t13req_msg'] = f"신청 {r['id']}번을 승인했습니다. 다음 시험부터 출제됩니다."; st.rerun()
                if n.button('반려', key=f"t13req_no_{r['id']}", width='stretch'):
                    accounts.decide_exam_request(admin, r['id'], False)
                    st.session_state['t13req_msg'] = f"신청 {r['id']}번을 반려했습니다."; st.rerun()
