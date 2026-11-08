"""AgentStream chatbot relay: browser -> this server (/api/t13/chat) -> AgentStream /open/v1.

The API key stays on this server. The browser only sees normalized NDJSON events:
  {"t":"meta","conversation_id":..}  {"t":"status","phase":..}  {"t":"delta","text":..}
  {"t":"sources","documents":[..]}   {"t":"chart","figures":[..],"manifest":{..}}
  {"t":"tool_failed","name":..}      {"t":"done"}   {"t":"error","code":..,"message":..}
Conversations are keyed by (visitor cookie, workspace, chatbot, our conversation id); a visitor can only
reach its own AgentStream session_id. Logs carry stage/status/content-type/elapsed/trace ids only.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets as pysecrets
import socket
import threading
import time
import tomllib
import uuid
from pathlib import Path

import anyio
import requests
import urllib3
import accounts
import knowledge
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

ROOT = Path(__file__).parent
SECRETS_FILE = ROOT / '.streamlit' / 'secrets.toml'
DEFAULTS = {
    'AGENTSTREAM_BASE_URL': 'https://api-gateway.jntp-ax.or.kr/agentstream',
    'AGENTSTREAM_WORKSPACE_ID': '9b219b9e-a9b3-4c92-a88f-c02951a1d4c5',
    'AGENTSTREAM_CHATBOT_ID': '183140a3-8fe2-4259-9df1-0befd12755f8',
}
MAX_QUESTION = 1000          # characters typed by the learner
MAX_CONTEXT = 8000           # characters of serialized inspection context
MAX_BODY = 64 * 1024         # bytes of the browser request
CONNECT_TIMEOUT, READ_TIMEOUT, TURN_TIMEOUT = 10, 120, 300  # seconds
CONV_TTL, CONV_CAP = 6 * 3600, 5000
COOKIE = 't13_vid'

log = logging.getLogger('t13.chat')
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('%(asctime)s %(name)s %(message)s'))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


# ------------------------------------------------------------------ settings (env first, then secrets.toml)
_secrets_cache = {'mtime': None, 'data': {}}


def setting(name):
    value = os.environ.get(name)
    if value:
        return value
    try:
        mtime = SECRETS_FILE.stat().st_mtime
        if mtime != _secrets_cache['mtime']:
            _secrets_cache.update(mtime=mtime, data=tomllib.loads(SECRETS_FILE.read_text(encoding='utf-8')))
        value = _secrets_cache['data'].get(name)
    except (OSError, tomllib.TOMLDecodeError):
        value = None
    return str(value) if value else DEFAULTS.get(name)


def api_url(path):
    return setting('AGENTSTREAM_BASE_URL').rstrip('/') + '/open/v1' + path


def headers():
    key = setting('AGENTSTREAM_API_KEY')
    if not key:
        raise UpstreamError('config', None, '챗봇 API 키가 서버에 설정되지 않았습니다. 관리자에게 AGENTSTREAM_API_KEY 설정을 요청해 주세요.')
    return {'X-API-Key': key, 'Content-Type': 'application/json', 'Accept': 'application/x-ndjson, application/json'}


# ------------------------------------------------------------------ errors
class UpstreamError(Exception):
    def __init__(self, stage, status, message, *, code='upstream', trace_id=None, reset=False, retry_after=None):
        super().__init__(message)
        self.stage, self.status, self.message, self.code = stage, status, message, code
        self.trace_id, self.reset, self.retry_after = trace_id, reset, retry_after


def explain(stage, resp):
    """Turn a non-success AgentStream response into a learner-facing UpstreamError (no secrets, short text)."""
    status = resp.status_code
    ctype = resp.headers.get('content-type', '')
    detail, trace = '', None
    if 'json' in ctype:
        try:
            body = resp.json()
            detail = str(body.get('message') or body.get('detail') or '')[:200]
            trace = body.get('trace_id')
        except (ValueError, AttributeError):
            pass
    retry = resp.headers.get('retry-after')
    suffix = f' ({detail})' if detail else ''
    if 300 <= status < 400:
        msg, code = f'외부 API가 다른 주소로 이동시켰습니다(HTTP {status}). 로그인 페이지 리다이렉트일 수 있어 따라가지 않았습니다.', 'redirect'
    elif 'text/html' in ctype:
        msg, code = f'외부 API 관문이 JSON 대신 웹페이지(HTML, HTTP {status})를 돌려줬습니다. 관문 오류이거나 로그인 페이지일 수 있습니다.', 'html'
    elif status == 401:
        msg, code = '챗봇 API 키가 없거나 유효하지 않습니다(HTTP 401). 관리자에게 키 설정을 확인해 달라고 요청해 주세요.', 'auth'
    elif status == 403:
        msg, code = '챗봇 호출 권한이 없습니다(HTTP 403). 챗봇 공개 설정·워크스페이스·호출 권한을 확인해야 합니다.' + suffix, 'forbidden'
    elif status == 404:
        msg, code = ('대화가 만료되었거나 찾을 수 없습니다(HTTP 404). 새 대화로 다시 질문해 주세요.' if stage == 'message'
                     else '챗봇을 찾을 수 없습니다(HTTP 404). API 주소와 챗봇 UUID를 확인해야 합니다.'), 'not_found'
    elif status == 422:
        msg, code = '질문 형식을 챗봇 서버가 받아들이지 않았습니다(HTTP 422).' + suffix, 'invalid'
    elif status == 429:
        msg, code = '요청이 많아 잠시 응답할 수 없습니다(HTTP 429).' + (f' {retry}초 후 다시 시도해 주세요.' if retry else ' 잠시 후 다시 시도해 주세요.'), 'rate_limited'
    elif status == 503:
        msg, code = '챗봇 서비스를 일시적으로 사용할 수 없습니다(HTTP 503).' + (f' {retry}초 후 다시 시도해 주세요.' if retry else ''), 'unavailable'
    elif status in (502, 504, 520):
        msg, code = f'외부 API 관문에서 처리에 실패했습니다(HTTP {status}). 우리 서버는 정상이며, 관문 또는 내부 모델 호출 구간의 문제일 수 있습니다.', 'gateway'
    else:
        msg, code = f'챗봇 서버 오류(HTTP {status}).' + suffix, 'upstream'
    return UpstreamError(stage, status, msg, code=code, trace_id=trace, reset=(status == 404 and stage == 'message'), retry_after=retry)


# ------------------------------------------------------------------ AgentStream calls (blocking; run in a worker thread)
def create_session(question):
    t0 = time.monotonic()
    resp = requests.post(api_url(f"/chatbots/{setting('AGENTSTREAM_CHATBOT_ID')}/sessions"), headers=headers(),
                         json={'query': question}, timeout=(CONNECT_TIMEOUT, 30), allow_redirects=False)
    ctype = resp.headers.get('content-type', '')
    log.info('stage=session status=%s ctype=%s elapsed=%.2fs', resp.status_code, ctype.split(';')[0], time.monotonic() - t0)
    if resp.status_code != 201 or 'json' not in ctype:
        raise explain('session', resp)
    try:
        sid = resp.json()['session_id']
    except (ValueError, KeyError, TypeError):
        sid = None
    if not isinstance(sid, str) or not sid:
        raise UpstreamError('session', 201, '챗봇 대화를 만들었지만 응답에 session_id가 없습니다.', code='bad_response')
    return sid


def open_message(session_id, message):
    t0 = time.monotonic()
    resp = requests.post(api_url(f'/chat-sessions/{session_id}/messages'), headers=headers(), json={'message': message},
                         stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), allow_redirects=False)
    ctype = resp.headers.get('content-type', '')
    log.info('stage=message status=%s ctype=%s first_byte=%.2fs', resp.status_code, ctype.split(';')[0], time.monotonic() - t0)
    if resp.status_code != 200 or 'ndjson' not in ctype:
        try:
            raise explain('message', resp)
        finally:
            resp.close()
    return resp


def abort_upstream(resp):
    """Stop an AgentStream stream without blocking the event loop.

    Response.close() waits for the buffered-reader lock, which the reader thread holds while it is blocked in
    recv(); calling it on the event loop would freeze the whole server. Shutting the socket down wakes that recv
    at once, and the close itself runs in a throwaway thread."""
    sock = getattr(getattr(getattr(resp, 'raw', None), '_connection', None), 'sock', None)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    threading.Thread(target=resp.close, daemon=True).start()


def health():
    t0 = time.monotonic()
    resp = requests.get(api_url(f"/chatbots/{setting('AGENTSTREAM_CHATBOT_ID')}/health"), headers=headers(),
                        timeout=(CONNECT_TIMEOUT, 20), allow_redirects=False)
    log.info('stage=health status=%s elapsed=%.2fs', resp.status_code, time.monotonic() - t0)
    if resp.status_code != 200 or 'json' not in resp.headers.get('content-type', ''):
        raise explain('health', resp)
    body = resp.json()
    return {'status': body.get('status', 'unknown'), 'message': body.get('message'), 'checked_at': body.get('checked_at'),
            'embedding_models': [{'status': m.get('status'), 'message': m.get('message')} for m in body.get('embedding_models') or [] if isinstance(m, dict)]}


# ------------------------------------------------------------------ NDJSON parsing and event translation (pure, unit-tested)
class BadStream(Exception):
    pass


class ClientGone(Exception):
    pass


class NdjsonBuffer:
    """Bytes in, parsed JSON objects out. Splits on b'\\n' before decoding, so a UTF-8 character or a JSON line
    split across chunks is reassembled; several lines in one chunk are all returned."""

    def __init__(self):
        self.buf = b''

    def feed(self, chunk):
        """Generator: complete lines are yielded one by one, so events before a bad line are not lost."""
        self.buf += chunk
        while b'\n' in self.buf:
            line, self.buf = self.buf.split(b'\n', 1)
            yield from self._parse(line)

    def close(self):
        line, self.buf = self.buf, b''
        return self._parse(line)

    @staticmethod
    def _parse(line):
        line = line.strip()
        if not line:
            return []
        try:
            obj = json.loads(line.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as e:
            raise BadStream('챗봇 응답에 해석할 수 없는 줄이 있었습니다.') from e
        if not isinstance(obj, dict):
            raise BadStream('챗봇 응답 형식이 예상과 다릅니다.')
        return [obj]


def delta_text(content):
    """assistant.delta content: a string, or a list of blocks of which only type=='text' is answer text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(b.get('text', '') for b in content
                       if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str))
    return ''


DOC_FIELDS = ('reference', 'title', 'document_title', 'file_name', 'filename', 'source', 'document_id', 'doc_id', 'id',
              'page', 'page_number', 'chunk_id', 'relevance_score', 'score', 'document', 'content', 'text', 'page_content')


def clean_document(doc):
    """Keep the provenance fields AgentStream gave (no invented sources). Scalars only, strings trimmed."""
    if not isinstance(doc, dict):
        return None
    pools = [doc] + [doc[k] for k in ('metadata', 'document') if isinstance(doc.get(k), dict)]
    out = {}
    for field in DOC_FIELDS:
        for pool in pools:
            v = pool.get(field)
            if isinstance(v, (str, int, float)) and not isinstance(v, bool) and field not in out:
                out[field] = v[:400] if isinstance(v, str) else v
    headings = doc.get('source_headings')
    if isinstance(headings, list) and headings:
        out['source_headings'] = ' > '.join(str(h) for h in headings if isinstance(h, (str, int)))[:200]
    return out or None


def chart_event(ev):
    outer = ev.get('artifact') if isinstance(ev.get('artifact'), dict) else {}
    art = outer.get('artifact') if isinstance(outer.get('artifact'), dict) else outer
    if art.get('kind') != 'visualization':
        return None
    payload = art.get('payload') if isinstance(art.get('payload'), dict) else {}
    figures, invalid = [], 0
    for f in payload.get('figures') or []:
        try:
            raw = f.get('content')
            fig = json.loads(raw) if isinstance(raw, str) else raw  # JSON only, never eval
            if not isinstance(fig, dict) or not isinstance(fig.get('data'), list):
                raise ValueError
            layout = fig.get('layout') if isinstance(fig.get('layout'), dict) else {}
            figures.append({'title': str(f.get('title') or '')[:200], 'data': fig['data'], 'layout': layout})
        except (AttributeError, ValueError, TypeError):
            invalid += 1
    m = payload.get('manifest') if isinstance(payload.get('manifest'), dict) else {}
    manifest = {k: m[k] for k in ('generated_count', 'failed_count', 'deferred_count') if isinstance(m.get(k), int)}
    return {'t': 'chart', 'figures': figures, 'manifest': manifest, 'invalid': invalid}


class TurnTranslator:
    """AgentStream events -> browser events. Drops duplicate event_ids, thinking/tool text and unknown events."""

    PHASES = {'request': '질문 확인 중', 'plan': '답변 계획 중', 'tool': '자료 검색 중', 'retriev': '자료 검색 중',
              'generat': '답변 작성 중', 'respon': '답변 작성 중'}

    def __init__(self):
        self.seen, self.completed, self.failed = set(), False, False
        self.turn_id, self.events, self.last_phase = None, 0, None

    def feed(self, ev):
        eid = ev.get('event_id')
        if eid is not None:
            if eid in self.seen:
                return []
            self.seen.add(eid)
        self.events += 1
        self.turn_id = self.turn_id or ev.get('turn_id')
        name = ev.get('event')
        if name == 'assistant.delta':
            text = delta_text(ev.get('content'))
            return [{'t': 'delta', 'text': text}] if text else []
        if name == 'agent.progress':
            phase = str(ev.get('phase') or '')
            label = next((v for k, v in self.PHASES.items() if k in phase), None)
            if label and label != self.last_phase:
                self.last_phase = label
                return [{'t': 'status', 'phase': label}]
            return []
        if name == 'tool.completed':
            art = ev.get('artifact')
            if isinstance(art, dict) and art.get('type') == 'rag_agent':
                docs = [d for d in (clean_document(x) for x in (art.get('documents') or [])[:10]) if d]
                return [{'t': 'sources', 'documents': docs, 'queries': [q for q in art.get('queries') or [] if isinstance(q, str)][:5]}]
            return []
        if name == 'tool.failed':
            return [{'t': 'tool_failed', 'name': str(ev.get('name') or '')[:60]}]
        if name == 'artifact.created':
            chart = chart_event(ev)
            return [chart] if chart else []
        if name == 'turn.completed':
            self.completed = True
            return [{'t': 'done'}]
        if name == 'turn.failed':
            self.failed = True
            err = ev.get('error') if isinstance(ev.get('error'), dict) else {}
            detail = str(err.get('message') or ev.get('message') or '')[:200]
            return [{'t': 'error', 'code': 'turn_failed', 'message': '챗봇이 답변을 끝내지 못했습니다.' + (f' ({detail})' if detail else '')}]
        return []


# ------------------------------------------------------------------ visitor identity and conversation ownership
_SIGNING_KEY = (os.environ.get('T13_SESSION_SECRET') or '').encode() or pysecrets.token_bytes(32)


def _sign(vid):
    return hmac.new(_SIGNING_KEY, vid.encode(), hashlib.sha256).hexdigest()[:32]


def visitor_of(request):
    """Return (visitor_id, is_new). The cookie is HMAC-signed so a client cannot claim another visitor's id."""
    raw = request.cookies.get(COOKIE, '')
    vid, _, sig = raw.partition('.')
    if vid and sig and hmac.compare_digest(sig, _sign(vid)):
        return vid, False
    return uuid.uuid4().hex, True


def set_visitor(response, request, vid):
    response.set_cookie(COOKIE, f'{vid}.{_sign(vid)}', max_age=CONV_TTL, httponly=True, samesite='lax',
                        secure=request.headers.get('x-forwarded-proto', request.url.scheme) == 'https',
                        path=request.scope.get('t13_base', '/') or '/')


class Conversation:
    def __init__(self):
        self.session_id, self.created, self.last = None, time.time(), time.time()
        self.lock = threading.Lock()


class Store:
    def __init__(self):
        self._d, self._lock = {}, threading.Lock()

    def _key(self, vid, cid):
        return (vid, setting('AGENTSTREAM_WORKSPACE_ID'), setting('AGENTSTREAM_CHATBOT_ID'), cid)

    def create(self, vid):
        with self._lock:
            self._prune()
            cid = uuid.uuid4().hex
            conv = self._d[self._key(vid, cid)] = Conversation()
            return cid, conv

    def get(self, vid, cid):
        with self._lock:
            conv = self._d.get(self._key(vid, cid)) if isinstance(cid, str) else None
            if conv:
                conv.last = time.time()
            return conv

    def drop(self, vid, cid):
        with self._lock:
            self._d.pop(self._key(vid, cid), None)

    def _prune(self):
        now = time.time()
        for k in [k for k, c in self._d.items() if now - c.last > CONV_TTL]:
            del self._d[k]
        while len(self._d) >= CONV_CAP:
            del self._d[min(self._d, key=lambda k: self._d[k].last)]


STORE = Store()


def chat_identity(request, vid):
    user = accounts.user_for_token(request.cookies.get(accounts.COOKIE))
    user_id = user['id'] if user else None
    return user_id, f'{vid}:{knowledge.scope(user_id)}'


# ------------------------------------------------------------------ request checks
def same_origin(request):
    """Reject cross-site calls: the custom header forces a CORS preflight we never answer, and Origin must match."""
    if request.headers.get('x-t13-chat') != '1':
        return False
    origin = request.headers.get('origin')
    if not origin:
        return True
    host = request.headers.get('x-forwarded-host') or request.headers.get('host', '')
    return origin.split('://', 1)[-1].rstrip('/') == host.split(',')[0].strip()


def _scalar(v):
    if v is None:
        return '없음'
    if isinstance(v, bool):
        return '예' if v else '아니요'
    return str(v)


def format_context(value, indent=''):
    """Inspection context as plain 'key: value' lines. Not a JSON code block: AgentStream treats JSON blocks in a
    message as a data table to analyse and rejects anything that is not a row array or a single result table."""
    lines = []
    for key, v in value.items():
        if isinstance(v, dict):
            lines.append(f'{indent}{key}:')
            lines.extend(format_context(v, indent + '  '))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            lines.append(f'{indent}{key}:')
            for row in v:
                if any(isinstance(x, dict) or (isinstance(x, list) and any(isinstance(y, dict) for y in x)) for x in row.values()):
                    lines.append(f'{indent}  -')
                    lines.extend(format_context(row, indent + '    '))
                else:
                    lines.append(f'{indent}  - ' + ' / '.join(f'{k}: {_scalar(x)}' for k, x in row.items()))
        elif isinstance(v, list):
            lines.append(f'{indent}{key}: ' + (', '.join(_scalar(x) for x in v) if v else '없음'))
        else:
            lines.append(f'{indent}{key}: {_scalar(v)}')
    return lines


def build_message(question, context):
    """Learner question, prefixed by the inspection context the stored prompt expects. No system/prompt fields."""
    if not context:
        return question
    notice = ('사진 파일은 제공되지 않았습니다. 사진을 직접 보았다고 말하거나 색상·질감·균열 모양 등의 시각적 근거를 만들지 마세요. '
              '판정·위치는 검사 모델이 반환한 정보로 설명하고, 제공되지 않은 위치·후보 번호는 추측하지 마세요. '
              '일반적인 관찰 기준은 사용자가 확인할 사항으로만 설명하세요.')
    return '<inspection_context>\n' + '\n'.join(format_context(context)) + '\n</inspection_context>\n\n' + notice + '\n\n' + question


class BodyTooLarge(Exception):
    pass


async def read_body(request):
    body = b''
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            raise BodyTooLarge
    data = json.loads(body.decode('utf-8') or '{}')
    if not isinstance(data, dict):
        raise ValueError('not an object')
    return data


def problem(status, message, **extra):
    return JSONResponse({'message': message, **extra}, status_code=status)


def line(obj):
    return (json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8')


# ------------------------------------------------------------------ routes
async def chat(request: Request):
    if not same_origin(request):
        return problem(403, '허용되지 않은 요청입니다.')
    try:
        data = await read_body(request)
    except BodyTooLarge:
        return problem(413, '요청이 너무 큽니다.')
    except ValueError:  # includes JSON and UTF-8 decode errors
        return problem(400, '요청 형식이 올바르지 않습니다.')
    question = data.get('message')
    if not isinstance(question, str) or not question.strip():
        return problem(422, '질문을 입력해 주세요.')
    question = question.strip()
    if len(question) > MAX_QUESTION:
        return problem(422, f'질문은 {MAX_QUESTION}자 이하로 입력해 주세요. (현재 {len(question)}자)')
    context = data.get('context')
    if context is not None and not isinstance(context, dict):
        return problem(422, '검사 정보 형식이 올바르지 않습니다.')
    if context and len(json.dumps(context, ensure_ascii=False)) > MAX_CONTEXT:
        return problem(422, '함께 보낼 검사 정보가 너무 큽니다. 새 대화로 다시 시도해 주세요.')

    vid, new_visitor = visitor_of(request)
    user_id, owner = await anyio.to_thread.run_sync(chat_identity, request, vid)
    cid = data.get('conversation_id')
    if cid:
        conv = None if new_visitor else STORE.get(owner, cid)
        if conv is None:  # unknown, expired, or someone else's conversation: never reveal which
            resp = problem(404, '이전 대화를 찾을 수 없습니다. 새 대화로 시작합니다. 질문을 다시 보내 주세요.', reset=True)
            if new_visitor:
                set_visitor(resp, request, vid)
            return resp
    else:
        cid, conv = STORE.create(owner)
    if conv.lock.locked():
        return problem(409, '이전 질문의 답변이 아직 생성 중입니다. 끝난 뒤 다시 보내 주세요.')

    context, review_cases = await anyio.to_thread.run_sync(knowledge.enrich, user_id, question, context)
    message = build_message(question, context)

    async def events():
        # The lock is taken inside the generator so it is always released by `finally` (a generator that never
        # starts because the browser left early never holds it).
        yield line({'t': 'meta', 'conversation_id': cid})
        yield line({'t': 'review_cases', 'cases': review_cases})
        if not conv.lock.acquire(blocking=False):
            yield line({'t': 'error', 'code': 'busy', 'message': '이전 질문의 답변이 아직 생성 중입니다. 끝난 뒤 다시 보내 주세요.'})
            return
        t0, tr, upstream, outcome = time.monotonic(), TurnTranslator(), None, 'ok'
        gone = asyncio.Event()

        async def watch_disconnect():
            # Browser cancelled or left: close the AgentStream stream at once (unblocks the reader thread).
            while (await request.receive())['type'] != 'http.disconnect':
                pass
            gone.set()
            if upstream is not None:
                abort_upstream(upstream)

        watcher = asyncio.create_task(watch_disconnect())
        try:
            if not conv.session_id:
                yield line({'t': 'status', 'phase': '대화 준비 중'})
                conv.session_id = await anyio.to_thread.run_sync(create_session, question, abandon_on_cancel=True)
            yield line({'t': 'status', 'phase': '질문 전송 중'})
            upstream = await anyio.to_thread.run_sync(open_message, conv.session_id, message, abandon_on_cancel=True)
            if gone.is_set():
                raise ClientGone
            parser = NdjsonBuffer()
            while True:
                if gone.is_set():
                    raise ClientGone
                # read1 returns whatever has arrived (chunked or not), so deltas are relayed as they come.
                chunk = await anyio.to_thread.run_sync(upstream.raw.read1, 65536, True, abandon_on_cancel=True)
                if not chunk:
                    break
                for ev in parser.feed(chunk):
                    for out in tr.feed(ev):
                        yield line(out)
                if time.monotonic() - t0 > TURN_TIMEOUT:
                    raise TimeoutError
            for ev in parser.close():
                for out in tr.feed(ev):
                    yield line(out)
            if not (tr.completed or tr.failed):
                outcome = 'incomplete'
                yield line({'t': 'error', 'code': 'incomplete', 'message': '답변이 완료 신호 없이 끝났습니다. 받은 내용까지만 표시합니다.'})
            elif tr.failed:
                outcome = 'turn_failed'
        except UpstreamError as e:
            outcome = f'{e.stage}:{e.status}'
            if e.reset:
                STORE.drop(owner, cid)
            log.info('stage=%s status=%s code=%s trace_id=%s', e.stage, e.status, e.code, e.trace_id)
            yield line({'t': 'error', 'code': e.code, 'message': e.message, 'reset': e.reset, 'retry_after': e.retry_after})
        except BadStream as e:
            outcome = 'bad_json'
            yield line({'t': 'error', 'code': 'bad_json', 'message': str(e) + ' 받은 내용까지만 표시합니다.'})
        except (TimeoutError, requests.Timeout, urllib3.exceptions.TimeoutError):
            outcome = 'timeout'
            yield line({'t': 'error', 'code': 'timeout', 'message': '챗봇 응답이 너무 오래 걸려 중단했습니다. 잠시 후 다시 시도해 주세요.'})
        except ClientGone:
            outcome = 'cancelled'
        except asyncio.CancelledError:
            outcome = 'cancelled'
            raise
        except Exception as e:  # noqa: BLE001 - a closed upstream raises assorted urllib3 errors
            if gone.is_set():
                outcome = 'cancelled'
            elif isinstance(e, (requests.RequestException, urllib3.exceptions.HTTPError, OSError)):
                outcome = 'network:' + type(e).__name__
                yield line({'t': 'error', 'code': 'network', 'message': '우리 서버에서 챗봇 서버로 연결하지 못했습니다(네트워크·DNS·TLS 구간).'})
            else:
                outcome = 'internal:' + type(e).__name__
                log.exception('stage=relay internal error')
                yield line({'t': 'error', 'code': 'internal', 'message': '우리 서버에서 답변을 중계하다 오류가 났습니다.'})
        finally:  # also runs when the browser disconnects or cancels
            watcher.cancel()
            if upstream is not None:
                abort_upstream(upstream)
            conv.lock.release()
            log.info('stage=turn outcome=%s events=%s completed=%s turn_id=%s elapsed=%.2fs',
                     outcome, tr.events, tr.completed, tr.turn_id, time.monotonic() - t0)

    resp = StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
    if new_visitor:
        set_visitor(resp, request, vid)
    return resp


async def reset(request: Request):
    if not same_origin(request):
        return problem(403, '허용되지 않은 요청입니다.')
    try:
        data = await read_body(request)
    except (BodyTooLarge, ValueError):
        data = {}
    vid, new_visitor = visitor_of(request)
    _, owner = await anyio.to_thread.run_sync(chat_identity, request, vid)
    if not new_visitor and isinstance(data.get('conversation_id'), str):
        STORE.drop(owner, data['conversation_id'])
    return JSONResponse({'ok': True})


async def chat_health(request: Request):
    try:
        return JSONResponse(await anyio.to_thread.run_sync(health))
    except UpstreamError as e:
        return problem(502, e.message, upstream_status=e.status)
    except requests.RequestException:
        return problem(502, '챗봇 서버에 연결하지 못했습니다.')


def routes(base_url_path=''):
    """Routes live under Streamlit's server.baseUrlPath so the hosting proxy forwards them like the page."""
    base = '/' + base_url_path.strip('/') if base_url_path and base_url_path.strip('/') else ''

    def with_base(handler):
        async def wrapped(request):
            request.scope['t13_base'] = (base or '') + '/'
            return await handler(request)
        return wrapped

    return [Route(base + '/api/t13/chat', with_base(chat), methods=['POST']),
            Route(base + '/api/t13/chat/reset', with_base(reset), methods=['POST']),
            Route(base + '/api/t13/chat/health', with_base(chat_health), methods=['GET'])]
