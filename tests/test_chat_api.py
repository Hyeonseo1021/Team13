"""Unit tests for the AgentStream relay's pure parts (no network)."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_api as c


def nd(*events):
    return b''.join((json.dumps(e, ensure_ascii=False) + '\n').encode() for e in events)


class NdjsonTests(unittest.TestCase):
    def test_split_utf8_and_lines_across_chunks(self):
        data = nd({'event': 'assistant.delta', 'content': '한글 답변'}, {'event': 'turn.completed'})
        cut = data.index('글'.encode()) + 1  # in the middle of a 3-byte character
        p = c.NdjsonBuffer()
        out = list(p.feed(data[:cut])) + list(p.feed(data[cut:cut + 3])) + list(p.feed(data[cut + 3:])) + p.close()
        self.assertEqual([e['event'] for e in out], ['assistant.delta', 'turn.completed'])
        self.assertEqual(out[0]['content'], '한글 답변')

    def test_many_lines_in_one_chunk_and_trailing_line_without_newline(self):
        p = c.NdjsonBuffer()
        out = list(p.feed(nd({'a': 1}, {'a': 2}) + b'\n\n{"a":3}'))
        self.assertEqual([e['a'] for e in out], [1, 2])
        self.assertEqual(p.close(), [{'a': 3}])

    def test_bad_json(self):
        with self.assertRaises(c.BadStream):
            list(c.NdjsonBuffer().feed(b'{"a":\n'))
        with self.assertRaises(c.BadStream):
            list(c.NdjsonBuffer().feed(b'[1,2]\n'))

    def test_events_before_a_bad_line_survive(self):
        got = []
        with self.assertRaises(c.BadStream):
            for e in c.NdjsonBuffer().feed(nd({'a': 1}) + b'{bad\n'):
                got.append(e)
        self.assertEqual(got, [{'a': 1}])


class TranslatorTests(unittest.TestCase):
    def test_text_only_dedup_and_completion(self):
        t = c.TurnTranslator()
        evs = [{'event': 'assistant.delta', 'event_id': 'x:1', 'content': '안녕'},
               {'event': 'assistant.delta', 'event_id': 'x:1', 'content': '안녕'},  # duplicate
               {'event': 'assistant.delta', 'event_id': 'x:2', 'content': [{'type': 'thinking', 'thinking': '비밀'}, {'type': 'text', 'text': '하세요'}]},
               {'event': 'assistant.delta', 'event_id': 'x:3', 'content': '', 'additional_kwargs': {'thinking_content': '생각'}},
               {'event': 'tool.completed', 'event_id': 'x:4', 'type': 'tool', 'content': '도구 원문', 'artifact': {'type': 'other'}},
               {'event': 'turn.completed', 'event_id': 'x:5', 'turn_id': 'T'}]
        out = [o for e in evs for o in t.feed(e)]
        self.assertEqual(''.join(o['text'] for o in out if o['t'] == 'delta'), '안녕하세요')
        self.assertEqual(out[-1], {'t': 'done'})
        self.assertTrue(t.completed)
        self.assertEqual(t.turn_id, 'T')

    def test_failures(self):
        t = c.TurnTranslator()
        self.assertEqual(t.feed({'event': 'tool.failed', 'name': '13rag'}), [{'t': 'tool_failed', 'name': '13rag'}])
        out = t.feed({'event': 'turn.failed', 'error': {'message': '모델 오류'}})
        self.assertEqual(out[0]['code'], 'turn_failed')
        self.assertIn('모델 오류', out[0]['message'])
        self.assertTrue(t.failed and not t.completed)

    def test_rag_sources_keep_given_fields_only(self):
        t = c.TurnTranslator()
        art = {'type': 'rag_agent', 'queries': ['q'], 'documents': [
            {'metadata': {'file_name': '기준서.pdf', 'page': 3}, 'page_content': '폼 두께 기준', 'vector': [0.1]}, 'junk']}
        out = t.feed({'event': 'tool.completed', 'artifact': art})
        self.assertEqual(out, [{'t': 'sources', 'queries': ['q'],
                                'documents': [{'file_name': '기준서.pdf', 'page': 3, 'page_content': '폼 두께 기준'}]}])
        self.assertEqual(t.feed({'event': 'tool.completed', 'artifact': {'type': 'rag_agent', 'documents': []}})[0]['documents'], [])
        real = {'document': 'FS-02. 균열·수축 관찰할 사항', 'reference': '폼스프레이_품질검사_RAG_지식베이스_v1.0.txt', 'relevance_score': 9.0,
                'scores': {'vector': 0.7}, 'source_headings': [], 'adjacent_evidence': [{'document': '...'}]}
        got = t.feed({'event': 'tool.completed', 'artifact': {'type': 'rag_agent', 'documents': [real]}})[0]['documents'][0]
        self.assertEqual(got, {'reference': real['reference'], 'relevance_score': 9.0, 'document': real['document']})

    def test_chart_artifact(self):
        fig = {'data': [{'type': 'bar', 'x': ['A'], 'y': [1]}], 'layout': {'title': {'text': 't'}}}
        ev = {'event': 'artifact.created', 'artifact': {'artifact': {'kind': 'visualization', 'payload': {
            'figures': [{'title': '막대', 'content': json.dumps(fig)}, {'title': '깨짐', 'content': '<script>x</script>'}],
            'manifest': {'generated_count': 2, 'failed_count': 1, 'deferred_count': 0}}}}}
        out = c.TurnTranslator().feed(ev)[0]
        self.assertEqual(out['t'], 'chart')
        self.assertEqual(len(out['figures']), 1)
        self.assertEqual(out['figures'][0]['data'], fig['data'])
        self.assertEqual(out['invalid'], 1)
        self.assertEqual(out['manifest'], {'generated_count': 2, 'failed_count': 1, 'deferred_count': 0})
        self.assertEqual(c.TurnTranslator().feed({'event': 'artifact.created', 'artifact': {'kind': 'table'}}), [])


class ErrorTests(unittest.TestCase):
    def resp(self, status, ctype='application/json', body=None, headers=None):
        r = Mock(status_code=status, headers={'content-type': ctype, **(headers or {})})
        r.json.return_value = body or {}
        return r

    def test_status_mapping(self):
        self.assertEqual(c.explain('session', self.resp(401)).code, 'auth')
        e = c.explain('session', self.resp(403, body={'message': '다른 조직', 'trace_id': 'tr'}))
        self.assertEqual((e.code, e.trace_id), ('forbidden', 'tr'))
        self.assertIn('다른 조직', e.message)
        self.assertTrue(c.explain('message', self.resp(404)).reset)
        self.assertFalse(c.explain('session', self.resp(404)).reset)
        self.assertIn('7초', c.explain('message', self.resp(429, headers={'retry-after': '7'})).message)
        self.assertEqual(c.explain('message', self.resp(502, 'text/html')).code, 'html')
        self.assertEqual(c.explain('message', self.resp(504)).code, 'gateway')
        self.assertEqual(c.explain('message', self.resp(302, 'text/html')).code, 'redirect')


class OwnershipTests(unittest.TestCase):
    def test_conversations_are_per_visitor(self):
        s = c.Store()
        cid, conv = s.create('alice')
        self.assertIs(s.get('alice', cid), conv)
        self.assertIsNone(s.get('bob', cid))
        s.drop('bob', cid)
        self.assertIs(s.get('alice', cid), conv)
        s.drop('alice', cid)
        self.assertIsNone(s.get('alice', cid))

    def test_cookie_signature(self):
        vid = 'abc'
        good = Mock(cookies={c.COOKIE: f'{vid}.{c._sign(vid)}'})
        self.assertEqual(c.visitor_of(good), ('abc', False))
        forged = Mock(cookies={c.COOKIE: f'{vid}.{"0" * 32}'})
        self.assertTrue(c.visitor_of(forged)[1])

    def test_same_origin(self):
        ok = Mock(headers={'x-t13-chat': '1', 'origin': 'https://site.example', 'host': 'site.example'})
        self.assertTrue(c.same_origin(ok))
        self.assertFalse(c.same_origin(Mock(headers={'origin': 'https://site.example', 'host': 'site.example'})))
        self.assertFalse(c.same_origin(Mock(headers={'x-t13-chat': '1', 'origin': 'https://evil.example', 'host': 'site.example'})))

    def test_message_has_context_but_no_prompt_fields(self):
        msg = c.build_message('왜 불량인가요?', {'검사 종류': '1. 표면 상태 분류', '요약': {'내 정답': 3}, '판정 클래스': ['A', 'B'],
                                               '사진별 결과': [{'사진': '사진 A', '촬영 위치': None}], '빈 목록': []})
        self.assertTrue(msg.startswith('<inspection_context>'))
        self.assertNotIn('```', msg)  # AgentStream would parse a JSON block as a data table
        for part in ('검사 종류: 1. 표면 상태 분류', '요약:\n  내 정답: 3', '판정 클래스: A, B', '  - 사진: 사진 A / 촬영 위치: 없음', '빈 목록: 없음'):
            self.assertIn(part, msg)
        self.assertTrue(msg.endswith('왜 불량인가요?'))
        self.assertEqual(c.build_message('질문', None), '질문')


if __name__ == '__main__':
    unittest.main()
