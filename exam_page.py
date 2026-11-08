"""?page=exam · 수행능력 평가 (시험).

Unlike 직접 판단 실습, this is a test of the learner alone: no model verdict, no LNG_NI chatbot, no hints.
Each inspection type contributes EXAM_PER_MODE photos from the labelled case sets; the learner marks every
photo 양품/불량, submits once, and gets a score with pass/fail. Logged-in results are saved (accounts.exams)."""
import html
import math
import time
from pathlib import Path

import streamlit as st

import accounts
from inspection import MODES, load_cases, case_thumb, pick_round, verdict
from ui import shell, fragment, footer, render_html

EXAM_PER_MODE = 5
PASS_RATE = 0.8
CHOICES = ['양품', '불량']
KEY = 't13exam'


def all_cases(mode):
    """Labelled case photos plus the questions the admin approved from learners' review records."""
    return load_cases(mode) + accounts.exam_pool(mode)


def build_exam():
    """[(mode, case), ...] in inspection order; each section mixes 양품 and 불량 in random amounts."""
    out = []
    for mode in MODES:
        cases = all_cases(mode)
        by_id = {c['id']: c for c in cases}
        out += [(mode, by_id[i]) for i in pick_round(cases, EXAM_PER_MODE)] if cases else []
    return out


def need(total):
    return math.ceil(total * PASS_RATE - 1e-9)


def fmt_time(sec):
    sec = int(sec or 0)
    return f'{sec // 60}분 {sec % 60:02d}초'


def title_block(sub):
    return ('<main id="workspace" tabindex="-1" class="exam-main"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 역량평가</div>'
            '<section class="workspace-title"><div class="title-main"><h1>수행능력 평가</h1>'
            f'<p>{sub}</p></div></section></main>')


def reset():
    for k in [k for k in st.session_state if k.startswith(KEY)]:
        st.session_state.pop(k, None)


def render():
    shell(None, no_chat=True, current='exam')
    state = st.session_state.setdefault(KEY, {})
    user = accounts.current_user()
    if 'result' in state:
        show_result(state, user)
    elif state.get('items'):
        take_exam(state)
    else:
        intro(state, user)
    fragment('<div class="ws-foot">' + footer() + '</div>')


def intro(state, user):
    total = EXAM_PER_MODE * len(MODES)
    fragment(title_block('실습에서 익힌 판정 능력을 혼자 힘으로 확인하는 시험입니다.'))
    rules = [
        ('문항 구성', f'검사 3종 × {EXAM_PER_MODE}문항, 모두 {total}문항입니다. 사진마다 <b>양품</b> 또는 <b>불량</b>을 고릅니다.'),
        ('합격 기준', f'{round(PASS_RATE * 100)}% 이상 ({need(total)}문항 이상) 맞히면 합격입니다.'),
        ('시험 중 제한', 'AI 모델 판정과 <i class="t13-brand">LNG_NI</i> 챗봇은 사용할 수 없습니다. 사진을 누르면 크게 볼 수 있습니다.'),
        ('제출과 기록', '모든 문항에 답해야 제출할 수 있고, 제출 후에는 답을 바꿀 수 없습니다. '
                     + ('결과는 마이페이지의 <b>내 시험 기록</b>에 저장됩니다.' if user else '<b>로그인하지 않으면 결과가 저장되지 않습니다.</b>')),
    ]
    boxes = ''.join(f'<section class="gd-box"><h3>{t}</h3><p>{d}</p></section>' for t, d in rules)
    fragment(f'<article class="gd-panel exam-intro"><div class="gd-grid two">{boxes}</div></article>')
    with st.container(key='t13exam_start'):
        a, b = st.columns([1, 1], gap='small')
        if a.button('검사 시작', type='primary', icon=':material/play_arrow:', width='stretch', key='t13exam_go'):
            reset()
            st.session_state[KEY] = {'items': [(m, c['id']) for m, c in build_exam()], 'start': time.time()}
            st.rerun()
        if not user:
            b.link_button('로그인하고 응시하기', '?page=login&next=%3Fpage%3Dexam', icon=':material/login:', width='stretch')
        else:
            b.link_button('내 시험 기록 보기', '?page=my&view=exams', icon=':material/history:', width='stretch')


def lookup(state):
    by = {m: {c['id']: c for c in all_cases(m)} for m in MODES}
    items = [(m, by[m].get(i)) for m, i in state['items']]
    if any(c is None for _, c in items):  # the photo set changed under a running exam
        return None
    return items


def take_exam(state):
    items = lookup(state)
    if items is None:
        reset(); st.rerun()
    total = len(items)
    answers = {n: st.session_state.get(f'{KEY}_q{n}') for n in range(total)}
    done = sum(v is not None for v in answers.values())
    fragment(title_block(f'사진마다 양품·불량을 고르세요. 모든 문항에 답하면 제출할 수 있습니다. · 답한 문항 <b>{done}</b> / {total}'))
    for mode, cfg in MODES.items():
        part = [(k, c) for k, (m, c) in enumerate(items) if m == mode]
        if not part:
            continue
        with st.container(border=True, key=f'{KEY}sec_{mode}'):
            fragment(f'<div class="step-head"><b>{cfg["number"]}</b><h3>{cfg["title"]} <small class="exam-sub">· {cfg["target"]}</small></h3></div>')
            with st.container(key=f't13examgrid_{mode}'):
                for col, (k, c) in zip(st.columns(len(part), gap='small'), part):
                    with col, st.container(border=True):
                        fragment(f'<p class="q-title">문항 {k + 1}</p>')
                        st.image(case_thumb(c['path'], Path(c['path']).stat().st_mtime, mode), width='stretch')
                        st.segmented_control(f'문항 {k + 1} 판정', CHOICES, key=f'{KEY}_q{k}', label_visibility='collapsed', width='stretch')
    left = total - done
    with st.container(key='t13exam_submit'):
        st.caption('모든 문항에 답했습니다. 제출하면 답을 바꿀 수 없습니다.' if not left else f'아직 답하지 않은 문항이 {left}개 있습니다.')
        a, b = st.columns([2, 1], gap='small')
        if a.button(f'답안 제출 · {done}/{total}', type='primary', disabled=bool(left), icon=':material/task_alt:', width='stretch', key='t13exam_submit_btn'):
            grade(state, items, answers)
            st.rerun()
        if b.button('처음부터 다시', icon=':material/restart_alt:', width='stretch', key='t13exam_restart'):
            reset(); st.rerun()


def grade(state, items, answers):
    detail = []
    for k, (mode, c) in enumerate(items):
        mine = answers[k] == '불량'
        detail.append({'no': k + 1, 'mode': mode, 'file': Path(c['path']).name, 'truth': verdict(c['defect']), 'cls': c['cls'],
                       'mine': verdict(mine), 'ok': mine == c['defect']})
    score = sum(d['ok'] for d in detail)
    seconds = time.time() - state.get('start', time.time())
    passed = score >= need(len(detail))
    state['scroll'] = True
    state['result'] = {'score': score, 'total': len(detail), 'passed': passed, 'seconds': seconds, 'detail': detail}
    user = accounts.current_user()
    if user:
        accounts.add_exam(user['id'], score, len(detail), passed, seconds, detail)
        state['saved'] = True


def show_result(state, user):
    r = state['result']
    items = lookup(state) or []
    pct = round(r['score'] * 100 / r['total']) if r['total'] else 0
    fragment(title_block('제출한 답안의 채점 결과입니다.'))
    per = ''.join(f'<li><span>{cfg["number"]}. {cfg["title"]}</span><b>{sum(d["ok"] for d in r["detail"] if d["mode"] == m)}</b> / {sum(d["mode"] == m for d in r["detail"])}</li>'
                  for m, cfg in MODES.items() if any(d['mode'] == m for d in r['detail']))
    saved = ('결과를 <a href="?page=my&amp;view=exams">내 시험 기록</a>에 저장했습니다.' if state.get('saved')
             else '로그인하지 않아 결과가 저장되지 않았습니다.')
    fragment(f'<section class="exam-score {"pass" if r["passed"] else "fail"}" aria-label="시험 결과">'
             f'<div class="exam-badge">{"합격" if r["passed"] else "불합격"}</div>'
             f'<div class="exam-num"><b>{r["score"]}</b> / {r["total"]}<small>{pct}점 · 합격 기준 {round(PASS_RATE * 100)}점 · 소요 {fmt_time(r["seconds"])}</small></div>'
             f'<ul class="exam-per">{per}</ul><p class="exam-saved">{saved}</p></section>')
    wrong = [d for d in r['detail'] if not d['ok']]
    with st.container(border=True, key='t13exam_review'):
        fragment('<div class="step-head"><h3>' + (f'틀린 문항 {len(wrong)}개' if wrong else '모든 문항을 맞혔습니다') + '</h3></div>')
        show = st.toggle('모든 문항 보기', key='t13exam_all', value=not wrong)
        rows = r['detail'] if show else wrong
        by_no = {k + 1: c for k, (m, c) in enumerate(items)}
        per_line = 5
        for mode, cfg in MODES.items():  # one titled group per inspection: "1. 표면 상태 분류 · 맞힘 3 / 5"
            part = [d for d in r['detail'] if d['mode'] == mode]
            if not part:
                continue
            got = sum(d['ok'] for d in part)
            shown = [d for d in rows if d['mode'] == mode]
            fragment(f'<div class="exam-group-head"><span class="exam-group-no">{cfg["number"]}</span><h4>{html.escape(cfg["title"])}</h4>'
                     f'<span class="exam-group-score {"ok" if got == len(part) else ""}">맞힘 {got} / {len(part)}</span>'
                     + ('' if got == len(part) else f'<a class="exam-group-go" href="?inspection={mode}">실습하러 가기 ›</a>') + '</div>')
            if not shown:
                fragment('<p class="exam-group-none">이 검사는 모두 맞혔습니다.</p>')
                continue
            for s in range(0, len(shown), per_line):
                chunk = shown[s:s + per_line]
                with st.container(key=f't13examres_{mode}_{s}'):
                    cols = st.columns(per_line, gap='small')
                    for col, d in zip(cols, chunk):
                        c = by_no.get(d['no'])
                        with col, st.container(border=True, key=f"t13qc{'ok' if d['ok'] else 'ng'}_ex{d['no']}"):
                            fragment(f'<p class="q-title">문항 {d["no"]}<span class="q-truth {"bad" if d["truth"] == "불량" else "good"}">정답 {d["truth"]}</span></p>')
                            if c:
                                st.image(case_thumb(c['path'], Path(c['path']).stat().st_mtime, d['mode']), width='stretch')
                            fragment('<div class="q-card">'
                                     f'<p class="q-line"><span>정답 클래스</span><b>{html.escape(d["cls"])}</b></p>'
                                     f'<p class="q-line"><span>내 답</span><b>{d["mine"]}</b><i class="{"ok" if d["ok"] else "ng"}">{"맞음" if d["ok"] else "틀림"}</i></p></div>')
        if wrong:
            st.caption('틀린 문항은 해당 검사의 직접 판단 실습에서 다시 연습해 보세요.')
    a, b = st.columns([1, 1], gap='small')
    if a.button('다시 응시하기', type='primary', icon=':material/refresh:', width='stretch', key='t13exam_again'):
        reset(); st.rerun()
    b.link_button('내 시험 기록 보기' if user else '로그인하기', '?page=my&view=exams' if user else '?page=login&next=%3Fpage%3Dexam',
                  icon=':material/history:', width='stretch')
    if state.pop('scroll', False):
        render_html('<span hidden></span>', "setTimeout(()=>document.querySelector('[data-testid=stMain]')?.scrollTo({top:0}),150)")
