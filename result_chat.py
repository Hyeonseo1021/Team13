"""Result-discussion chatbot: summarises an inspection result and discusses it with the learner (Claude API).

Key: ANTHROPIC_API_KEY in .streamlit/secrets.toml (or the environment). Never sent to the browser.
"""
import base64
import io
import json
import os

import anthropic
import streamlit as st

MODEL = 'claude-opus-5-5'
API_URL = 'https://api.anthropic.com'  # pinned: the host shell may export a different ANTHROPIC_BASE_URL

SYSTEM = """당신은 LNG 탱크 품질검사를 배우는 신입직원을 돕는 'LNG_NI'입니다.
학습자는 사진을 보고 먼저 자신의 예상을 고른 뒤, AI 검사 모델(분류 ViT, 탐지 EfficientDet, 분할 MaskDINO)의 결과와 비교합니다.
대화에 주어지는 [검사 결과] JSON이 유일한 사실 근거입니다. 그 밖의 수치나 판정을 지어내지 마세요.

원칙:
- 한국어로, 짧고 쉽게 답합니다. 첫 요약은 4~6문장 이내.
- 첫 요약에서는 (1) 모델 결과 (2) 내 예상과의 일치 여부 (3) 정답이 있으면 정답과의 비교 (4) 주의할 점 하나를 말하고, 학습자가 생각해 볼 토론 질문 하나로 끝냅니다.
- 모델 점수는 확률적 신뢰도일 뿐 정답률이나 합격 판정이 아닙니다. 분류 모델에는 '해당 없음' 클래스가 없고, 탐지·분할에서 후보가 없다는 것이 양품을 뜻하지 않습니다.
- 사진이 함께 주어지면 사진에서 보이는 근거를 들어 토론하되, 확실하지 않은 것은 확실하지 않다고 말합니다.
- 실제 현장 판정은 기업 검사 기준과 담당자 검토가 필요하다는 점을 필요할 때 상기시킵니다.
- 학습자가 정답만 묻기보다 스스로 근거를 찾도록 되묻는 방식으로 토론을 이끕니다."""


def api_key():
    try:
        key = st.secrets.get('ANTHROPIC_API_KEY')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        key = None
    return key or os.environ.get('T13_ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')


@st.cache_resource
def _client(key):
    return anthropic.Anthropic(api_key=key, base_url=API_URL, timeout=120.0, max_retries=2)


def image_block(image, side=1024):
    small = image.copy()
    small.thumbnail((side, side))
    buf = io.BytesIO()
    small.convert('RGB').save(buf, format='JPEG', quality=85)
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode('ascii')}}


def first_turn(context, images=()):
    """Opening user turn: the result JSON (+ photos) and a request for the short summary."""
    content = [image_block(im) for im in images]
    content.append({'type': 'text', 'text': '[검사 결과]\n' + json.dumps(context, ensure_ascii=False, indent=1) + '\n\n이 검사 결과를 간단히 요약해 주고, 토론을 시작해 주세요.'})
    return {'role': 'user', 'content': content}


def stream_reply(messages):
    """Yield text chunks from Claude. Raises RuntimeError with a learner-friendly message on failure."""
    key = api_key()
    if not key:
        raise RuntimeError('LLM이 아직 연결되지 않았습니다. 관리자가 ANTHROPIC_API_KEY를 설정하면 토론을 시작할 수 있습니다.')
    try:
        with _client(key).beta.messages.stream(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            messages=messages,
            output_config={'effort': 'low'},
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
        if final.stop_reason == 'refusal':
            yield '\n\n(이 질문에는 답변할 수 없습니다. 다른 방식으로 질문해 주세요.)'
        elif final.stop_reason == 'max_tokens':
            yield '\n\n(답변이 길어 중간에 끊겼습니다.)'
    except anthropic.AuthenticationError as e:
        raise RuntimeError('LLM API 키가 올바르지 않습니다. 관리자에게 키 설정을 확인해 달라고 요청해 주세요.') from e
    except anthropic.RateLimitError as e:
        raise RuntimeError('요청이 많아 잠시 응답할 수 없습니다. 잠시 후 다시 시도해 주세요.') from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f'LLM 서버 오류 (HTTP {e.status_code}). 잠시 후 다시 시도해 주세요.') from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError('LLM 서버에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요.') from e


def render_chat(chat_id, title, context, images=()):
    """Inline discussion panel. History lives in session_state[chat_id]: API messages + display log."""
    state = st.session_state.setdefault(chat_id, {'api': [], 'log': []})
    head = st.columns([5, 1])
    head[0].markdown(f':material/forum: **{title}**')
    if head[1].button('닫기', key=chat_id + ':close', width='stretch'):
        st.session_state.pop('t13_chat_target', None)
        st.rerun()
    if not api_key():
        st.info('LLM 미연결 상태입니다. `ANTHROPIC_API_KEY`를 설정하면 결과 요약과 토론이 동작합니다.')
        return
    box = st.container(height=460)
    for role, text in state['log']:
        box.chat_message(role, avatar=':material/person:' if role == 'user' else ':material/smart_toy:').markdown(text)
    pending = None
    if not state['api']:
        state['api'].append(first_turn(context, images))
        pending = True
    question = st.chat_input('결과에 대해 질문하거나 의견을 적어 보세요', key=chat_id + ':input', max_chars=1000)
    if question:
        state['api'].append({'role': 'user', 'content': question})
        state['log'].append(('user', question))
        box.chat_message('user', avatar=':material/person:').markdown(question)
        pending = True
    if pending:
        with box.chat_message('assistant', avatar=':material/smart_toy:'):
            try:
                text = st.write_stream(stream_reply(state['api']))
            except RuntimeError as e:
                state['api'].pop()  # let the learner retry the same turn
                if state['log'] and state['log'][-1][0] == 'user':
                    state['log'].pop()
                st.error(str(e))
                return
        state['api'].append({'role': 'assistant', 'content': text})
        state['log'].append(('assistant', text))
    if st.button('대화 다시 시작', key=chat_id + ':reset'):
        st.session_state.pop(chat_id, None)
        st.rerun()
