"""'AI 판정 검토' practice + the shared answer-review dialog (오답 복습 · AI 확신도).

Review task: the learner uploads a photo, the inspection API immediately proposes a verdict, and
the learner approves it or rejects it with the correct judgement. Nothing is precomputed and no
ground truth is needed; each decision is kept as a review record (current session only).
"""
import csv
import hashlib
import html
import io
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

import inspection as ins
from ui import fragment

APPROVE, REJECT = '승인', '거절'
NO_DEFECT = '양품 (불량 없음)'


def chat_button():
    fragment('<button type="button" class="run-chat-btn" data-chat aria-controls="chat-panel" aria-label="학습 도우미 챗봇 열기"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 4H3v14h5l4 4v-4h9ZM7 9h10M7 13h6"/></svg>챗봇</button>')


def score_text(score):
    return f'{score*100:.1f}%' if score is not None else '-'


def correction_choices(mode, view):
    """What the learner may choose instead of the AI verdict when rejecting it."""
    classes = ins.MODES[mode]['classes']
    if mode == 'classification':
        return [c for c in classes if c != view['label']]
    defects = [c for c in classes if ins.is_defect_class(c)]
    return ([NO_DEFECT] if view['defect'] else []) + defects  # a defect the learner does not see / a defect the AI missed


# ------------------------------------------------------------------ AI confidence (shared)
def confidence(mode, body, image=None, show_overlay=True):
    """AI 확신도: class probability bars (classification) or boxes/masks + candidate list (detection/segmentation)."""
    if mode == 'classification':
        part = body[mode]
        rows = sorted(zip(ins.MODES[mode]['classes'], part['probabilities']), key=lambda x: -x[1])
        bars = ''.join(f'<li class="{"top" if i == 0 else ""}"><span>{html.escape(n)}</span><i style="width:{max(p*100,0.6):.1f}%"></i><b>{p*100:.1f}%</b></li>' for i, (n, p) in enumerate(rows))
        fragment('<p class="conf-title">AI 확신도 · 클래스별 확률</p><ul class="conf-bars">' + bars + '</ul>')
        return
    items = body[mode]['detections' if mode == 'detection' else 'instances']
    if show_overlay and image is not None:
        found = [x for x in items if x['score'] >= ins.SHOW_SCORE]
        try: st.image(ins.overlay(image, found, mode == 'segmentation'), caption=f'점수 {ins.SHOW_SCORE} 이상 후보 {len(found)}개', width='stretch')
        except (ValueError, TypeError, OverflowError): pass
    top = sorted(items, key=lambda x: -x['score'])[:5]
    fragment('<p class="conf-title">AI 확신도 · 상위 후보</p><ul class="conf-bars">' + (''.join(
        f'<li class="{"top" if i == 0 else ""}"><span>{html.escape(x["class"]["name"])}</span><i style="width:{x["score"]*100:.1f}%"></i><b>{x["score"]*100:.1f}%</b></li>' for i, x in enumerate(top)) or '<li><span>후보 없음</span><i style="width:0"></i><b>-</b></li>') + '</ul>')


def open_review(title, entries, mode):
    """Answer-review dialog for the judge quiz. entries: {name, path, truth, truth_defect, mine, ai, body, ok, tip}."""
    @st.dialog(title, width='large')
    def _dialog():
        wrong = [e for e in entries if not e['ok']]
        shown = wrong or entries
        st.caption(f'틀린 사진 {len(wrong)}장' + ('을 정답과 AI 확신도와 함께 다시 봅니다.' if wrong else ' · 모두 맞혔습니다. 사진별 AI 확신도를 확인해 보세요.'))
        idx = st.session_state.get('t13_rev_idx', 0) % len(shown)
        e = shown[idx]
        a, b = st.columns([1.2, 1], gap='medium')
        with a:
            st.image(ins.case_thumb(e['path'], Path(e['path']).stat().st_mtime, mode, 1100), width='stretch')
        with b:
            fragment(f'<p class="q-title">{html.escape(e["name"])}<span class="q-truth {"bad" if e["truth_defect"] else "good"}">정답 {html.escape(e["truth"])}</span></p>'
                     f'<p class="q-line"><span>내 판단</span><b>{html.escape(e["mine"])}</b><i class="{"ok" if e["ok"] else "ng"}">{"맞음" if e["ok"] else "틀림"}</i></p>'
                     f'<p class="q-line"><span>AI 판정</span><b>{html.escape(e["ai"])}</b></p>'
                     + (f'<p class="rev-tip">{html.escape(e["tip"])}</p>' if e.get('tip') else ''))
            if e.get('body'):
                image = ins.read_image(Path(e['path']).read_bytes(), mode)[0] if mode != 'classification' else None
                confidence(mode, e['body'], image)
                fragment('<p class="conf-note">확률이 높아도 정답을 보장하지 않습니다. 사진에서 근거를 직접 확인하세요.</p>')
        if len(shown) > 1:
            p, mid, n = st.columns([1, 2, 1], vertical_alignment='center')
            if p.button('‹ 이전', key='t13_rev_prev', width='stretch'):
                st.session_state.t13_rev_idx = idx - 1; st.rerun(scope='fragment')
            mid.markdown(f"<p style='text-align:center;margin:0'>{idx+1} / {len(shown)}</p>", unsafe_allow_html=True)
            if n.button('다음 ›', key='t13_rev_next', width='stretch'):
                st.session_state.t13_rev_idx = idx + 1; st.rerun(scope='fragment')
    st.session_state.t13_rev_idx = 0
    _dialog()


# ------------------------------------------------------------------ review task (upload -> AI suggestion -> decision)
def log_csv(log):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['검토 시각', '사진', 'AI 판정', 'AI 점수', '내 결정', '내 판정'])
    for r in log: w.writerow([r['time'], r['file'], r['ai'], r['score'], r['decision'], r['mine']])
    return '﻿' + buf.getvalue()


def open_log(log):
    @st.dialog('검토 기록', width='large')
    def _dialog():
        st.caption('현재 브라우저 세션에만 보관되며 서버 파일로 저장하지 않습니다.')
        st.dataframe([{'검토 시각': r['time'], '사진': r['file'], 'AI 판정': r['ai'], 'AI 점수': r['score'], '내 결정': r['decision'], '내 판정': r['mine']} for r in log], hide_index=True, width='stretch')
        st.download_button('CSV로 내려받기', log_csv(log), file_name='team13-ai-review-log.csv', mime='text/csv', icon=':material/download:')
    _dialog()


def render_review(mode, cfg, cases=None):
    key = 'rv_' + mode
    state = st.session_state.setdefault(key, {'n': 0, 'ai': {}, 'log': []})
    with st.container(border=True, key='t13step1'):
        fragment('<div class="step-row">' + ins.step(1, '사진을 올리면 AI가 판정을 제안합니다') + (
            f'<ul class="q-summary" aria-label="검토 기록 요약"><li>검토 <b>{len(state["log"])}</b>건</li>'
            f'<li>승인 <b>{sum(r["decision"] == APPROVE for r in state["log"])}</b></li><li>거절 <b>{sum(r["decision"] == REJECT for r in state["log"])}</b></li></ul>' if state['log'] else '') + '</div>')
        left, right = st.columns([1, 1.05], gap='medium')
        image = body = view = None
        with left:
            file = st.file_uploader(f"{cfg['target']} 사진 (JPEG/PNG)", type=['jpg', 'jpeg', 'png'], key=f"{key}_up_{state['n']}",
                                    help='최대 10 MiB, 최대 20,000,000픽셀. 올리는 즉시 지정된 검사 API로 전송되며 사이트에는 저장되지 않습니다.')
            if file:
                data = file.getvalue()
                try:
                    image, mime = ins.read_image(data, mode)
                    sig = hashlib.sha256(data).hexdigest()
                    if sig not in state['ai']:
                        with st.spinner('AI가 사진을 판정하고 있습니다…'):
                            state['ai'][sig] = ins.call_model(mode, data, mime)
                    body = state['ai'][sig]; view = ins.model_view(mode, body)
                except ValueError as e:
                    st.error(str(e)); image = None
            if image is not None:
                with st.container(key='t13rvimg'):
                    if mode == 'classification': st.image(image, width='stretch')
                    else:
                        items = body[mode]['detections' if mode == 'detection' else 'instances']
                        try: st.image(ins.overlay(image, [x for x in items if x['score'] >= ins.SHOW_SCORE], mode == 'segmentation'), width='stretch')
                        except (ValueError, TypeError, OverflowError): st.image(image, width='stretch')
            else:
                st.caption('사진을 올리면 바로 AI 판정이 나오고, 오른쪽에서 승인 또는 거절합니다.')
        with right:
            if view is None:
                fragment('<div class="empty-result rv-empty"><svg viewBox="0 0 96 96" aria-hidden="true"><rect x="14" y="20" width="68" height="52" rx="6"/><path d="m22 62 18-18 12 12 8-8 14 14"/><circle cx="62" cy="36" r="6"/></svg>'
                         '<h3>AI 제안이 이곳에 표시됩니다</h3><p>AI 판정을 그대로 믿지 말고, 사진에서 근거를 직접 확인한 뒤 승인하거나 거절하세요.</p></div>')
                decision = choice = None
            else:
                fragment(f'<div class="rv-ai"><span class="rv-ai-label">AI 제안</span><b class="q-truth {"bad" if view["defect"] else "good"}">{ins.verdict(view["defect"])}</b>'
                         f'<strong>{html.escape(view["label"])}</strong><span class="rv-ai-score">{score_text(view["score"])}</span></div>')
                confidence(mode, body, show_overlay=False)
                decision = st.segmented_control('AI 제안에 대한 내 결정', [APPROVE, REJECT], key=f"{key}_dec_{state['n']}", width='stretch', label_visibility='collapsed')
                choice = None
                if decision == REJECT:
                    choice = st.selectbox('올바른 판정', correction_choices(mode, view), index=None, placeholder='거절 사유: 올바른 판정 선택', key=f"{key}_fix_{state['n']}", label_visibility='collapsed')
            ready = view is not None and (decision == APPROVE or (decision == REJECT and choice))
            with st.container(key='t13runrow_review'):
                run, chat = st.columns([4, 1.4], gap='small', vertical_alignment='center')
                if run.button('검토 기록하고 다음 사진', type='primary', disabled=not ready, width='stretch', key=f'{key}_save'):
                    state['log'].append({'time': datetime.now(ZoneInfo('Asia/Seoul')).strftime('%H:%M:%S'), 'file': file.name,
                                         'ai': f"{ins.verdict(view['defect'])} · {view['label']}", 'score': score_text(view['score']),
                                         'decision': decision, 'mine': choice or f"{ins.verdict(view['defect'])} · {view['label']}"})
                    state['n'] += 1; st.rerun()
                with chat: chat_button()
        if state['log']:
            last = state['log'][-1]
            a, b = st.columns([3, 1.2], gap='small', vertical_alignment='center')
            a.caption(f"최근 기록 {last['time']} · {last['file']} · AI {last['ai']} → {last['decision']}" + (f" ({last['mine']})" if last['decision'] == REJECT else ''))
            if b.button('검토 기록 보기', icon=':material/list_alt:', width='stretch', key=f'{key}_log'):
                open_log(state['log'])
