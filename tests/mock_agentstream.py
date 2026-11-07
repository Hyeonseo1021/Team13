"""Local stand-in for AgentStream /open/v1, for relay tests without the real service.

Run:  python tests/mock_agentstream.py 8598   then start the app with
      AGENTSTREAM_BASE_URL=http://127.0.0.1:8598/agentstream AGENTSTREAM_API_KEY=test  (mock only checks that a key is present)
Scenario is picked by a keyword in the message: SPLIT, FAIL, CUT, BADJSON, CHART, SLOW, HTTP429, HTML, else a
normal answer. Responses are synthetic test data, never shown as real chatbot output.
"""
import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SESSIONS = {}


def ev(event, n, **kw):
    return {'event': event, 'event_id': f'T:{n}', 'turn_id': 'T', **kw}


def lines(*events):
    return b''.join((json.dumps(e, ensure_ascii=False) + '\n').encode() for e in events)


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get('content-length') or 0)) or b'{}')

    def send(self, status, obj, ctype='application/json'):
        data = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('content-type', ctype)
        self.send_header('content-length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.headers.get('x-api-key'):
            return self.send(401, {'message': 'bad key'})
        if self.path.endswith('/health'):
            return self.send(200, {'status': 'healthy', 'message': 'mock', 'checked_at': 'now', 'embedding_models': []})
        self.send(404, {'message': 'nf'})

    def do_POST(self):
        if not self.headers.get('x-api-key'):
            return self.send(401, {'message': 'bad key'})
        b = self.body()
        if self.path.endswith('/sessions'):
            sid = str(uuid.uuid4())
            SESSIONS[sid] = []
            return self.send(201, {'session_id': sid, 'title': b.get('query')})
        if '/chat-sessions/' in self.path and self.path.endswith('/messages'):
            sid = self.path.split('/chat-sessions/')[1].split('/')[0]
            if sid not in SESSIONS:
                return self.send(404, {'message': 'no session'})
            msg = b.get('message', '')
            SESSIONS[sid].append(msg)
            if 'HTTP429' in msg:
                self.send_response(429)
                self.send_header('retry-after', '9')
                self.send_header('content-type', 'application/json')
                self.send_header('content-length', '2')
                self.end_headers()
                return self.wfile.write(b'{}')
            if 'HTML' in msg:
                return self.send(502, b'<html>bad gateway</html>', 'text/html')
            self.send_response(200)
            self.send_header('content-type', 'application/x-ndjson')
            self.send_header('connection', 'close')
            self.end_headers()
            w = self.wfile
            ctx = 'yes' if msg.startswith('<inspection_context>') else 'no'
            turn = len(SESSIONS[sid])
            if 'SPLIT' in msg:
                data = lines(ev('assistant.delta', 1, content='분할 '), ev('assistant.delta', 1, content='분할 '),
                             ev('assistant.delta', 2, content=[{'type': 'thinking', 'thinking': 'X'}, {'type': 'text', 'text': '한글 응답'}]),
                             ev('turn.completed', 3))
                cut = data.index('한'.encode()) + 1
                for part in (data[:7], data[7:cut], data[cut:]):
                    w.write(part); w.flush(); time.sleep(0.05)
                return
            if 'FAIL' in msg:
                return w.write(lines(ev('assistant.delta', 1, content='부분 답변'), ev('turn.failed', 2, error={'message': 'mock failure'})))
            if 'CUT' in msg:
                return w.write(lines(ev('assistant.delta', 1, content='끊긴 답변')))
            if 'BADJSON' in msg:
                return w.write(lines(ev('assistant.delta', 1, content='앞부분')) + b'{not json\n')
            if 'CHART' in msg:
                fig = json.dumps({'data': [{'type': 'bar', 'x': ['양품', '불량'], 'y': [10, 10]}], 'layout': {'title': {'text': '테스트 차트'}}})
                art = {'artifact': {'kind': 'visualization', 'payload': {'figures': [{'title': '합성 막대', 'content': fig}],
                                                                         'manifest': {'generated_count': 1, 'failed_count': 0, 'deferred_count': 1}}}}
                return w.write(lines(ev('tool.completed', 1, type='tool', artifact={'type': 'rag_agent', 'queries': ['q'], 'documents': [{'metadata': {'file_name': '합성기준서.pdf', 'page': 2}, 'page_content': '합성 근거'}]}),
                                     ev('artifact.created', 2, artifact=art), ev('assistant.delta', 3, content='차트를 만들었습니다.'), ev('turn.completed', 4)))
            if 'SLOW' in msg:
                for i in range(60):
                    w.write(lines(ev('assistant.delta', i + 1, content=f'{i} '))); w.flush(); time.sleep(0.25)
                return w.write(lines(ev('turn.completed', 99)))
            w.write(lines(ev('agent.progress', 1, phase='request.validating'),
                          ev('tool.completed', 2, type='tool', artifact={'type': 'rag_agent', 'documents': []}),
                          ev('assistant.delta', 3, content=f'[대역 응답] turn={turn} context={ctx}'), ev('turn.completed', 4)))
            return
        self.send(404, {'message': 'nf'})


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8598), H).serve_forever()
