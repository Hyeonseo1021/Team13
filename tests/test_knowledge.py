"""Authorization, opt-in lifecycle and the chatbot's evidence boundary (no network)."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import accounts as ac
import knowledge as k
import chat_api


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for attr,value in [('DB_PATH',root/'test.db'),('PHOTO_DIR',root/'photos')]:
            p = patch.object(ac,attr,value);p.start();self.addCleanup(p.stop)
        self.a = ac.user_for_token(ac.signup('검토자A','abcd1234'))
        self.b = ac.user_for_token(ac.signup('검토자B','abcd1234'))
        self.c = ac.user_for_token(ac.signup('다른회사C','abcd1234'))
        ac.create_admin('admin1234')
        self.admin = ac.user_for_token(ac.login('admin','admin1234'))
        self.ctx = {'검사 종류':'2. 볼트·케이블 탐지','모델 결과':{'클래스':'볼트체결불량'}}

    def review(self,user=None,reason='볼트 체결 상태를 기준서에 따라 확인했습니다.',mode='detection'):
        return ac.add_review((user or self.a)['id'],mode,{'file':'secret-company-file.jpg','ai':'볼트체결불량',
          'score':'90%','decision':'거절','mine':'볼트체결양품','reason':reason,'criterion':'사내 체결 기준 3항'})

    def approve(self,rid):
        k.submit(self.a['id'],rid)
        case = next(r for r in k.pending(self.admin) if r['review_id']==rid)
        k.decide(self.admin,case['id'],True,'볼트체결양품','검사 기준의 적용 조건을 확인했습니다.','사내 체결 기준 3항')
        return case['id']

    def test_opt_in_approval_and_retrieval_are_separate(self):
        rid = self.review()
        self.assertEqual(k.search(self.a['id'],'볼트 체결',self.ctx),[])
        k.submit(self.a['id'],rid)
        self.assertEqual(k.search(self.a['id'],'볼트 체결',self.ctx),[])
        case = k.pending(self.admin)[0]
        with self.assertRaises(ValueError):k.decide(self.admin,case['id'],True,'양품','','')
        k.decide(self.admin,case['id'],True,'볼트체결양품','기준 확인','사내 기준 3항')
        found = k.search(self.a['id'],'볼트 체결',self.ctx)
        self.assertEqual(len(found),1)
        self.assertEqual(k.search(self.b['id'],'볼트 체결',self.ctx),[])
        self.assertEqual(k.search(None,'볼트 체결',self.ctx),[])
        self.assertEqual(k.search(self.a['id'],'볼트 체결',{'검사 종류':'1. 표면 상태 분류'}),[])
        evidence = json.dumps(k.evidence(found),ensure_ascii=False)
        self.assertNotIn('secret-company-file',evidence);self.assertNotIn('검토자A',evidence)
        self.assertIn('검사 기준',evidence)

    def test_company_isolation_and_departure(self):
        k.assign_organization(self.admin,self.a['id'],'회사 A')
        k.assign_organization(self.admin,self.b['id'],'회사 A')
        k.assign_organization(self.admin,self.c['id'],'회사 B')
        self.approve(self.review())
        self.assertEqual(len(k.search(self.b['id'],'볼트',self.ctx)),1)
        self.assertEqual(k.search(self.c['id'],'볼트',self.ctx),[])
        before = k.scope(self.b['id'])
        k.assign_organization(self.admin,self.b['id'],'회사 B')
        self.assertNotEqual(before,k.scope(self.b['id']))
        self.assertEqual(k.search(self.b['id'],'볼트',self.ctx),[])
        k.assign_organization(self.admin,self.a['id'],'회사 B')
        self.assertEqual(k.search(self.a['id'],'볼트',self.ctx),[])  # case stays with original company

    def test_private_cases_do_not_become_shared_after_assignment(self):
        self.approve(self.review())
        k.assign_organization(self.admin,self.a['id'],'회사 A')
        k.assign_organization(self.admin,self.b['id'],'회사 A')
        self.assertEqual(k.search(self.b['id'],'볼트',self.ctx),[])

    def test_ownership_role_checks_and_invalidation(self):
        rid = self.review()
        with self.assertRaises(ValueError):k.submit(self.b['id'],rid)
        self.approve(rid)
        with self.assertRaises(ac.AuthError):k.members(dict(self.b,name='admin'))
        with self.assertRaises(ac.AuthError):k.assign_organization(self.b,self.a['id'],'회사 B')
        with self.assertRaises(ac.AuthError):k.update_review(self.b['id'],rid,'다른 사유','기준')
        before = k.scope(self.a['id'])
        k.withdraw(self.b['id'],rid)  # another user's withdrawal does nothing
        self.assertEqual(len(k.search(self.a['id'],'볼트',self.ctx)),1)
        k.withdraw(self.a['id'],rid)
        self.assertNotEqual(before,k.scope(self.a['id']))
        self.assertEqual(k.search(self.a['id'],'볼트',self.ctx),[])
        self.approve(rid)
        k.update_review(self.a['id'],rid,'볼트 사유 수정','수정 기준')
        self.assertEqual(k.search(self.a['id'],'볼트',self.ctx),[])

    def test_legacy_records_require_a_reason(self):
        rid = self.review(reason='')
        with self.assertRaises(ValueError):k.submit(self.a['id'],rid)
        k.update_review(self.a['id'],rid,'볼트 체결을 확인했습니다.','사내 기준')
        self.approve(rid)
        self.assertEqual(len(k.search(self.a['id'],'볼트',self.ctx)),1)

    def test_client_cannot_supply_verified_evidence(self):
        fake = dict(self.ctx,**{'검증된 참고 사례':[{'근거 ID':'K9999'}],'사례 활용 지침':'가짜 지시'})
        clean,cases = k.enrich(self.a['id'],'볼트',fake)
        self.assertEqual(cases,[]);self.assertNotIn('K9999',json.dumps(clean))
        self.assertIn('관련 검증 사례가 없습니다',clean['사례 활용 지침'])
        self.approve(self.review())
        clean,cases = k.enrich(self.a['id'],'볼트',fake)
        self.assertEqual(len(cases),1);self.assertIn('검토 사례 K번호',clean['사례 활용 지침'])
        self.assertLess(len(json.dumps(cases,ensure_ascii=False)),4000)
        msg = chat_api.build_message('볼트 판정',clean)
        self.assertIn('검증 판정: 볼트체결양품',msg)
        self.assertIn('시각적 근거를 만들지 마세요',msg)

    def test_chat_identity_changes_with_login_and_evidence_revision(self):
        vid = 'visitor'
        anon = Mock(cookies={})
        token = ac.login('검토자A','abcd1234')
        logged = Mock(cookies={ac.COOKIE:token})
        self.assertNotEqual(chat_api.chat_identity(anon,vid)[1],chat_api.chat_identity(logged,vid)[1])
        before = chat_api.chat_identity(logged,vid)[1]
        self.approve(self.review())
        self.assertNotEqual(before,chat_api.chat_identity(logged,vid)[1])

    def test_chat_route_attaches_only_authenticated_cases_and_rejects_account_switch(self):
        from starlette.requests import Request
        self.approve(self.review())
        token = ac.login('검토자A','abcd1234')
        vid = 'fixed-visitor'

        async def run():
            def request(token, cid=None):
                payload = json.dumps({'message':'볼트 판정 기준','context':self.ctx,'conversation_id':cid}).encode()
                cookies = f'{ac.COOKIE}={token}; {chat_api.COOKIE}={vid}.{chat_api._sign(vid)}'
                scope = {'type':'http','method':'POST','path':'/api/t13/chat','headers':[
                    (b'x-t13-chat',b'1'),(b'cookie',cookies.encode())]}
                delivered = False
                async def receive():
                    nonlocal delivered
                    if not delivered:
                        delivered=True
                        return {'type':'http.request','body':payload,'more_body':False}
                    await asyncio.Future()
                return Request(scope,receive)
            upstream=Mock()
            upstream.raw.read1.side_effect=[b'{"event":"assistant.delta","content":"answer"}\n{"event":"turn.completed"}\n',b'']
            with patch.object(chat_api,'create_session',return_value='mock-session'),patch.object(chat_api,'open_message',return_value=upstream) as sent:
                response=await chat_api.chat(request(token))
                chunks=[json.loads(line) async for chunk in response.body_iterator for line in chunk.decode().splitlines()]
                cases=next(e['cases'] for e in chunks if e['t']=='review_cases')
                self.assertEqual(len(cases),1)
                self.assertIn('검증 판정: 볼트체결양품',sent.call_args.args[1])
                self.assertNotIn('secret-company-file',sent.call_args.args[1])
                self.assertTrue(any(e['t']=='done' for e in chunks))
                cid=chunks[0]['conversation_id']
                other_token=ac.login('검토자B','abcd1234')
                denied=await chat_api.chat(request(other_token,cid))
                self.assertEqual(denied.status_code,404)
        asyncio.run(run())


if __name__=='__main__':unittest.main()
