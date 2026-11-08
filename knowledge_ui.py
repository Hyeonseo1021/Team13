"""Review-case consent, verification and organization membership controls."""
import streamlit as st
import accounts
import knowledge as k


def case_controls(user, selected, key, scope='app'):
    org = k.organization(user['id'])
    destination = f"{org['name']} 소속 사용자" if org else '본인'
    states = {c['review_id']:c for c in k.own_cases(user['id'])}
    if not selected:
        st.caption('기록을 선택하면 사유를 보완하거나 챗봇 참고 사례로 신청할 수 있습니다.')
        return
    if len(selected) == 1:
        r = selected[0]
        with st.expander('검토 사유·검사 기준 보완'):
            with st.form(f'{key}_reason_{r["id"]}'):
                reason = st.text_area('검토 사유', value=r.get('reason',''), max_chars=1500)
                criterion = st.text_input('적용한 검사 기준·문서 조항 (선택)', value=r.get('criterion',''), max_chars=300)
                if st.form_submit_button('사유 저장'):
                    try:
                        k.update_review(user['id'],r['id'],reason,criterion)
                    except (ValueError,accounts.AuthError) as e:
                        st.error(str(e))
                    else:
                        st.rerun(scope=scope)
            st.caption('사유를 수정하면 기존 사례 활용은 철회됩니다. 다시 신청하여 검증받을 수 있습니다.')
    for r in selected:
        case = states.get(r['id'])
        if case:
            st.caption(f"검토 기록 {r['id']} · 사례 K{case['id']} · {case['status']} · 활용 범위: {case['organization'] or '본인'}")
            if case.get('expert_note'):
                st.text('검증 의견: ' + case['expert_note'])
    # 사례 활용 동의 체크박스 · 사례 검증 신청 / 활용 철회 버튼과 안내 문구는 사용자 요청으로 마이페이지에서 뺐다 (2026-11-08).


def admin_panel(admin):
    if not accounts.is_admin(admin):
        return
    with st.container(border=True,key='t13_knowledge_admin'):
        st.subheader('챗봇 참고 사례 검증')
        st.caption('관리자가 해당 분야의 판정과 기준을 확인한 사례만 승인하세요. 승인 자체가 실제 현장 판정의 정확성을 보장하지는 않습니다.')
        waiting = k.pending(admin)
        if not waiting:
            st.info('검증 대기 중인 사례가 없습니다.')
        for r in waiting:
            with st.expander(f"K{r['id']} · {r['organization'] or '개인 사례'} · {r['mode']}"):
                st.text(f"AI 판정: {r['ai']}\n검토자 판정: {r['mine']}\n검토 사유: {r['reason']}\n제출 기준: {r['criterion'] or '미기재'}")
                with st.form(f"case_verify_{r['id']}"):
                    label = st.text_input('검증한 최종 판정',value=r['mine'] or '',max_chars=160)
                    standard = st.text_input('확인한 검사 기준·문서 조항',value=r['criterion'] or '',max_chars=300)
                    note = st.text_area('검증 의견·적용 조건',max_chars=1200)
                    approve = st.form_submit_button('검증 승인',type='primary')
                    reject = st.form_submit_button('반려')
                if approve or reject:
                    try:
                        k.decide(admin,r['id'],approve,label,note,standard)
                    except (ValueError,accounts.AuthError) as e:
                        st.error(str(e))
                    else:
                        st.rerun()
    with st.expander('기업 소속 관리'):
        st.caption('소속을 지정하면 해당 회사에 공유된 검증 사례를 검색할 수 있습니다. 기존 사례의 공유 범위는 이동하지 않습니다. 소속을 해제하려면 회사 이름을 비우세요.')
        users = k.members(admin)
        if users:
            with st.form('knowledge_membership'):
                selected = st.selectbox('계정',users,format_func=lambda u:f"{u['name']} · {u['organization'] or '소속 없음'}")
                name = st.text_input('회사 이름',max_chars=80)
                if st.form_submit_button('소속 적용'):
                    try:
                        k.assign_organization(admin,selected['id'],name)
                    except (ValueError,accounts.AuthError) as e:
                        st.error(str(e))
                    else:
                        st.rerun()
