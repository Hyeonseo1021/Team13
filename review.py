"""'AI 판정 검토' practice + the shared answer-review dialog (오답 복습 · AI 확신도).

Review task: the learner uploads a photo, the inspection API immediately proposes a verdict, and
the learner uploads up to 30 photos (drag and drop), reviews them one at a time, and approves it or rejects it with the correct judgement. Nothing is precomputed and no
ground truth is needed; each decision is saved for the logged-in user on the server (accounts.py). With the
reviewer's consent a reduced copy of the photo is kept for accounts.PHOTO_DAYS days, viewable only by its owner.
"""
import base64
import csv
import hashlib
import html
import io
from pathlib import Path

import streamlit as st

import accounts
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
COLUMNS = [('created', '검토 시각'), ('mode', '검사 종류'), ('file', '사진'), ('ai', 'AI 판정'), ('score', 'AI 점수'), ('decision', '내 결정'), ('mine', '내 판정')]


def _row(r):
    return {label: (ins.MODES[r[k]]['title'] if k == 'mode' and r.get(k) in ins.MODES else r.get(k, '')) for k, label in COLUMNS}


def log_csv(log):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow([label for _, label in COLUMNS])
    for r in log: w.writerow(list(_row(r).values()))
    return '\ufeff' + buf.getvalue()


@st.cache_data(max_entries=600, show_spinner=False)
def _photo_thumb(path, mtime, edge):
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert('RGB'); im.thumbnail((edge, edge))
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=75)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def photo_uri(user, r, edge=160):
    """The owner's stored photo as an inline data URI (never a public URL); '' when none is kept."""
    path = accounts.photo_file(user['id'], r.get('photo'))
    if not path:
        return ''
    try:
        return _photo_thumb(str(path), path.stat().st_mtime, edge)
    except (OSError, ValueError):
        return ''


def log_view(user, key='t13_log', in_dialog=False, mode=None):
    """The user's saved records: photo thumbnails, select a row to enlarge, CSV download, delete all photos.
    Used by the review-tab dialog and by 마이페이지 (?page=my). mode filters to one inspection type."""
    scope = 'fragment' if in_dialog else 'app'
    accounts.purge_old_photos()
    log = accounts.reviews_for(user['id'], mode)
    kept = sum(bool(r.get('photo')) for r in log)
    st.caption(f'서버에 저장된 기록 {len(log)}건 (최신순) · 사진 {kept}장 보관 중 · 사진은 검토일로부터 {accounts.PHOTO_DAYS}일 뒤 자동 삭제되고, 본인만 볼 수 있습니다.')
    if not log:
        st.info('아직 저장된 검토 기록이 없습니다. AI 판정 검토에서 사진을 검토하면 이곳에 쌓입니다.')
        return
    rows = [dict({'미리보기': photo_uri(user, r)}, **_row(r)) for r in log]
    picked = st.dataframe(rows, hide_index=True, width='stretch', row_height=64, on_select='rerun', selection_mode='single-row',
                          column_config={'미리보기': st.column_config.ImageColumn('미리보기', width='small')}, key=f'{key}_table')
    sel = (picked.selection.rows if picked else []) or []
    if sel and sel[0] < len(log):
        r = log[sel[0]]
        big = accounts.photo_file(user['id'], r.get('photo'))
        if big:
            st.image(big.read_bytes(), caption=f"{r['file']} · {r['created']} · {r['decision']}", width='stretch' if in_dialog else 720)
        else:
            st.caption('이 기록에는 보관된 사진이 없습니다. (동의하지 않았거나, 보관 기간이 지났거나, 사진 저장 전 기록입니다.)')
    else:
        st.caption('행을 선택하면 사진을 크게 볼 수 있습니다.')
    a, b = st.columns([1, 1], vertical_alignment='center')
    a.download_button('CSV로 내려받기', log_csv(log), file_name='team13-ai-review-log.csv', mime='text/csv', icon=':material/download:', key=f'{key}_csv')
    if kept:
        ask = f'{key}_del_ask'
        if st.session_state.get(ask):
            b.warning(f'보관된 사진 {kept}장을 모두 지웁니다. 검토 기록(텍스트)은 남습니다.')
            y, n = b.columns(2)
            if y.button('삭제', type='primary', key=f'{key}_del_yes', width='stretch'):
                accounts.delete_photos(user['id']); st.session_state[ask] = False; st.rerun(scope=scope)
            if n.button('취소', key=f'{key}_del_no', width='stretch'):
                st.session_state[ask] = False; st.rerun(scope=scope)
        elif b.button('내 사진 모두 삭제', icon=':material/delete:', key=f'{key}_del', width='stretch'):
            st.session_state[ask] = True; st.rerun(scope=scope)


def open_log(user):
    @st.dialog(f"{user['name']} 님의 검토 기록", width='large')
    def _dialog():
        log_view(user, 't13_log', in_dialog=True)
    st.session_state.t13_log_del_ask = False
    _dialog()


MAX_PHOTOS = 30


def thumb_uri(state, sig, data):
    """Small base64 JPEG for the queue strip (cached per photo in the session)."""
    th = state.setdefault('th', {})
    if sig not in th:
        try:
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB'); im.thumbnail((120, 120))
            buf = io.BytesIO(); im.save(buf, 'JPEG', quality=70)
            th[sig] = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            th[sig] = ''
    return th[sig]


def queue_strip(state, items, current):
    cells = []
    for i, (sig, f, _) in enumerate(items):
        st_ = state['done'].get(sig)
        cls = 'on' if sig == current else (('ok' if st_ == APPROVE else 'ng' if st_ == REJECT else 'skip') if st_ else '')
        mark = {APPROVE: '승인', REJECT: '거절', '건너뜀': '건너뜀'}.get(st_, '검토 중' if sig == current else '대기')
        src = thumb_uri(state, sig, f.getvalue())
        cur = ' aria-current="true"' if sig == current else ''
        img = f'<img src="{src}" alt="">' if src else '<span class="rq-noimg"></span>'
        cells.append(f'<li class="{cls}" title="{html.escape(f.name)} · {mark}"{cur}>{img}<b>{i+1}</b>'
                     f'<span class="sr-only">{i+1}번 {html.escape(f.name)} {mark}</span></li>')
    fragment('<ul class="rv-queue" aria-label="올린 사진 검토 순서">' + ''.join(cells) + '</ul>')


def render_review(mode, cfg, cases=None):
    key = 'rv_' + mode
    state = st.session_state.setdefault(key, {'n': 0, 'ai': {}, 'log': []})
    state.setdefault('done', {})
    user = accounts.current_user()
    if not user:
        from urllib.parse import urlencode
        href = '?' + urlencode({'page': 'login', 'next': f'?inspection={mode}&task=review'})
        with st.container(border=True, key='t13step1'):
            fragment('<div class="rv-login"><svg class="icon" viewBox="0 0 24 24" width="44" height="44" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/></svg>'
                     '<h3>로그인 후 AI 판정 검토를 시작할 수 있습니다</h3><p>누가 어떤 판정을 승인·거절했는지 기록하기 위해 로그인이 필요합니다.</p>'
                     f'<a class="login-submit" href="{html.escape(href)}">로그인 / 회원가입</a></div>')
        return {'단계': '로그인 전', '안내': '로그인해야 AI 판정 검토를 시작할 수 있습니다.'}
    mine = accounts.reviews_for(user['id'], mode)
    ctx = {'단계': '사진 업로드 전'}
    with st.container(border=True, key='t13step1'):
        fragment('<div class="step-row">' + ins.step(1, f'사진을 최대 {MAX_PHOTOS}장 올리면 한 장씩 AI 판정을 검토합니다') + (
            f'<ul class="q-summary" aria-label="내 검토 기록 요약 (이 검사)"><li>내 검토 <b>{len(mine)}</b>건</li>'
            f'<li>승인 <b>{sum(r["decision"] == APPROVE for r in mine)}</b></li><li>거절 <b>{sum(r["decision"] == REJECT for r in mine)}</b></li>'
            f'<li class="rv-log-li"><a class="rv-log-link" href="?page=my&amp;view=records">내 검토 기록 보기 <span aria-hidden="true">›</span></a></li></ul>' if mine else '') + '</div>')
        left, right = st.columns([1, 1.15], gap='medium')
        with left, st.container(key='t13rvleft'):
            consent = st.checkbox(f'사진 보관 동의 · 축소본을 서버에 {accounts.PHOTO_DAYS}일 보관',
                                  key=f"t13_photo_ok_{user['id']}",
                                  help=f'검토한 사진을 긴 변 {accounts.PHOTO_EDGE}px로 줄이고 위치정보 등 메타데이터를 지운 뒤 보관합니다. 동의하면 검토 기록에 사진이 함께 남아 나중에 다시 볼 수 있습니다. 본인만 볼 수 있고, 기록 화면에서 언제든 지울 수 있습니다. '
                                       '동의하지 않아도 검토할 수 있으며 이때는 기록(텍스트)만 저장됩니다. 회사 보안 규정상 반출이 금지된 현장 사진은 올리지 마세요.')
            top = st.container(key='t13rvqueue')
            files = st.file_uploader(f"{cfg['target']} 사진 (JPEG/PNG, 최대 {MAX_PHOTOS}장)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True,
                                     key=f"{key}_up_{state['n']}",
                                     help=f'여러 장을 끌어다 놓거나 선택하세요. 최대 {MAX_PHOTOS}장, 장당 최대 10 MiB. 검토하는 사진은 지정된 검사 API로 전송됩니다. 사이트 보관 여부는 위 동의 항목을 따릅니다.') or []
            items, seen = [], set()
            for f in files:
                data = f.getvalue(); sig = hashlib.sha256(data).hexdigest()
                if sig not in seen: seen.add(sig); items.append((sig, f, data))
            if len(items) > MAX_PHOTOS:
                st.warning(f'사진은 최대 {MAX_PHOTOS}장까지 검토합니다. 앞의 {MAX_PHOTOS}장만 사용하고 {len(items) - MAX_PHOTOS}장은 제외했습니다.')
                items = items[:MAX_PHOTOS]
            pending = [it for it in items if it[0] not in state['done']]
            current = pending[0] if pending else None
            with top:  # progress + thumbnails sit above the upload box, so the box can stretch to the bottom
                if items:
                    done_n = len(items) - len(pending)
                    fragment(f'<p class="rq-progress"><b>{done_n}</b> / {len(items)}장 검토' + ('' if pending else ' · 모두 완료') + '</p>')
                    queue_strip(state, items, current[0] if current else None)
        with right:
            image = body = view = None
            if current:
                sig, file, data = current
                try:
                    image, mime = ins.read_image(data, mode)
                    if sig not in state['ai']:
                        with st.spinner(f'AI가 {html.escape(file.name)}을(를) 판정하고 있습니다…'):
                            state['ai'][sig] = ins.call_model(mode, data, mime)
                    body = state['ai'][sig]; view = ins.model_view(mode, body)
                except ValueError as e:
                    ctx = {'단계': 'AI 판정 실패', '사진': file.name, '오류': str(e)}
                    st.error(f'{file.name}: {e}')
                    if st.button('이 사진 건너뛰기', icon=':material/skip_next:', key=f'{key}_skip_{sig[:12]}'):
                        state['done'][sig] = '건너뜀'; st.rerun()
            if view is not None:
                pic, info = st.container(key='t13rvpair').columns([1, 1.1], gap='small')
                pic_ctx = pic.container(key='t13rvimg')
                with pic_ctx:
                    if mode == 'classification': st.image(image, width='stretch')
                    else:
                        items_ = body[mode]['detections' if mode == 'detection' else 'instances']
                        try: st.image(ins.overlay(image, [x for x in items_ if x['score'] >= ins.SHOW_SCORE], mode == 'segmentation'), width='stretch')
                        except (ValueError, TypeError, OverflowError): st.image(image, width='stretch')
                with pic: fragment(f'<p class="rq-name" title="{html.escape(file.name)}">{html.escape(file.name)}</p>')
                with info:
                  fragment(f'<div class="rv-ai"><span class="rv-ai-label">AI 제안</span><b class="q-truth {"bad" if view["defect"] else "good"}">{ins.verdict(view["defect"])}</b>'
                         f'<strong>{html.escape(view["label"])}</strong><span class="rv-ai-score">{score_text(view["score"])}</span></div>')
                  confidence(mode, body, show_overlay=False)
                dec_key = f"{key}_{state['n']}_{sig[:12]}"
                decision = st.segmented_control('AI 제안에 대한 내 결정', [APPROVE, REJECT], key=f'{dec_key}_dec', width='stretch', label_visibility='collapsed')
                choice = None
                if decision == REJECT:
                    choice = st.selectbox('올바른 판정', correction_choices(mode, view), index=None, placeholder='거절 사유: 올바른 판정 선택', key=f'{dec_key}_fix', label_visibility='collapsed')
                ctx = {'단계': '사진 검토 중 (결정 전)' if not decision else f'사진 검토 중 ({decision} 선택, 기록 전)',
                       '사진': file.name, 'AI 제안': f"{ins.verdict(view['defect'])} · {view['label']} {score_text(view['score'])}",
                       '모델 결과': ins.model_summary(mode, body), '내 결정': decision or '아직 선택하지 않음'}
                if decision == REJECT: ctx['내가 고른 올바른 판정'] = choice or '아직 선택하지 않음'
                if mode != 'classification': ctx['화면 표시 기준'] = f'점수 {ins.SHOW_SCORE} 이상 후보만 사진에 표시'
            elif current is None and items:
                ctx = {'단계': '올린 사진 검토 완료'}
                fragment('<div class="empty-result rv-empty rv-done"><svg viewBox="0 0 96 96" aria-hidden="true"><circle cx="48" cy="48" r="34"/><path d="m32 49 11 11 22-24"/></svg>'
                         f'<h3>{len(items)}장 검토를 마쳤습니다</h3><p>검토 기록을 확인하거나 새 사진을 올려 계속 검토하세요.</p></div>')
                decision = choice = None
            else:
                if not current:
                    fragment('<div class="empty-result rv-empty"><svg viewBox="0 0 96 96" aria-hidden="true"><rect x="14" y="20" width="68" height="52" rx="6"/><path d="m22 62 18-18 12 12 8-8 14 14"/><circle cx="62" cy="36" r="6"/></svg>'
                             '<h3>AI 제안이 이곳에 표시됩니다</h3><p>AI 판정을 그대로 믿지 말고, 사진에서 근거를 직접 확인한 뒤 승인하거나 거절하세요.</p></div>')
                decision = choice = None
            ready = view is not None and (decision == APPROVE or (decision == REJECT and choice))
            with st.container(key='t13runrow_review'):
                run, chat = st.columns([4, 1.4], gap='small', vertical_alignment='center')
                if current is None and items:
                    if run.button('새 사진 올리기', type='primary', icon=':material/upload:', width='stretch', key=f'{key}_new'):
                        state['n'] += 1; state['done'] = {}; st.rerun()
                elif run.button('검토 기록하고 다음 사진' if len(pending) > 1 else '검토 기록하기', type='primary', disabled=not ready, width='stretch', key=f'{key}_save'):
                    rec = {'file': file.name, 'sig': sig, 'ai': f"{ins.verdict(view['defect'])} · {view['label']}", 'score': score_text(view['score']),
                           'decision': decision, 'mine': choice or f"{ins.verdict(view['defect'])} · {view['label']}"}
                    try:
                        accounts.add_review(user['id'], mode, rec, photo=data if consent else None)
                    except Exception:
                        st.error('검토 기록을 서버에 저장하지 못했습니다. 잠시 뒤 다시 눌러 주세요.'); st.stop()
                    state['done'][sig] = decision; st.rerun()
                with chat: chat_button()
    if items:
        done = [state['done'][s] for s, _, _ in items if s in state['done']]
        ctx['이번 묶음 진행'] = {'올린 사진': len(items), '검토 완료': len(done), '승인': done.count(APPROVE), '거절': done.count(REJECT), '건너뜀': done.count('건너뜀')}
    ctx['정답 라벨'] = '없음 (직접 올린 사진이라 정답이 없습니다. 사진의 근거로 AI 판정을 검토하는 단계입니다)'
    if mine:
        ctx['내 누적 검토 (이 검사)'] = {'전체': len(mine), '승인': sum(r['decision'] == APPROVE for r in mine), '거절': sum(r['decision'] == REJECT for r in mine)}
        ctx['최근 검토 기록 (최대 5건)'] = [{'사진': r.get('file'), 'AI 판정': r.get('ai'), '내 결정': r.get('decision'), '내 판정': r.get('mine')} for r in mine[:5]]
    return ctx
