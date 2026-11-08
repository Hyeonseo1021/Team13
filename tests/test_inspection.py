import io,json,sys,unittest
from unittest.mock import patch,Mock
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import numpy as np
from pycocotools import mask as masks
import inspection as m

class InspectionTests(unittest.TestCase):
 def setUp(self):
  im=Image.new('RGB',(12,8),'gray');b=io.BytesIO();im.save(b,format='PNG');self.data=b.getvalue()
 def test_inputs(self):
  image,mime=m.read_image(self.data,'classification');self.assertEqual(image.size,(12,8));self.assertEqual(mime,'image/png')
  for data in [b'',b'bad',b'x'*(m.MAX_BYTES+1)]:
   with self.assertRaises(ValueError):m.read_image(data,'detection')
  b=io.BytesIO();Image.new('RGB',(2,2)).save(b,format='GIF')
  with self.assertRaises(ValueError):m.read_image(b.getvalue(),'segmentation')
 def test_mpo_is_jpeg(self):
  b=io.BytesIO();Image.new('RGB',(12,8),'gray').save(b,format='MPO',save_all=True,append_images=[Image.new('RGB',(6,4))])
  self.assertEqual(Image.open(io.BytesIO(b.getvalue())).format,'MPO');self.assertEqual(m.read_image(b.getvalue(),'classification')[1],'image/jpeg')
  plain=m.api_bytes(b.getvalue());im=Image.open(io.BytesIO(plain));self.assertEqual(im.format,'JPEG');self.assertEqual(im.size,(12,8))
  self.assertEqual(m.api_bytes(self.data),self.data)
 def test_exif(self):
  b=io.BytesIO();im=Image.new('RGB',(12,8));ex=Image.Exif();ex[274]=6;im.save(b,format='JPEG',exif=ex)
  self.assertEqual(m.read_image(b.getvalue(),'classification')[0].size,(12,8))
  self.assertEqual(m.read_image(b.getvalue(),'detection')[0].size,(8,12))
 def test_request_contracts(self):
  fixtures={'classification':{'class':{'name':'表面'},'score':.8,'probabilities':[.1,.8,.05,.05]},'detection':{'detections':[]},'segmentation':{'instances':[]}}
  for mode,part in fixtures.items():
   with patch.object(m.requests,'post',return_value=Mock(ok=True,json=lambda:{mode:part})) as req:
    result=m.call_model(mode,self.data,'image/png');self.assertIn(mode,result)
    self.assertEqual(req.call_args.args[0],m.BASE+'/predict/'+mode)
    self.assertEqual(req.call_args.kwargs['files']['file'][1],self.data)
 def test_errors(self):
  with patch.object(m.requests,'post',side_effect=m.requests.Timeout):
   with self.assertRaisesRegex(ValueError,'계속될'):m.call_model('classification',self.data,'image/png')
  with patch.object(m.requests,'post',return_value=Mock(ok=False,status_code=429,headers={'Retry-After':'1'},json=lambda:{'detail':'busy'})):
   with self.assertRaisesRegex(ValueError,'429'):m.call_model('detection',self.data,'image/png')
  with self.assertRaises(ValueError):m.validate_result({'classification':{'class':{'name':'x'},'score':float('nan')}},'classification')
 def test_mask_alignment(self):
  a=np.zeros((8,12),dtype=np.uint8,order='F');a[2:6,3:9]=1;r=masks.encode(a)
  item={'class':{'name':'균열'},'score':.9,'bbox_xyxy':[3,2,9,6],'mask_rle':{'size':r['size'],'counts':r['counts'].decode('ascii')}}
  image,_=m.read_image(self.data,'segmentation');out=m.overlay(image,[item],True)
  self.assertEqual(out.size,image.size);self.assertNotEqual(out.getpixel((5,4)),image.getpixel((5,4)))
  item['mask_rle']['size']=[2,2]
  with self.assertRaises(ValueError):m.overlay(image,[item],True)
 def test_quiz_cases_from_demo_folder(self):
  cases=m.load_cases('classification')
  self.assertGreater(len(cases),0);self.assertTrue(any(c['defect'] for c in cases));self.assertTrue(any(not c['defect'] for c in cases))
  self.assertTrue(all((c['cls']=='폼스프레이불량')==c['defect'] for c in cases))
  self.assertTrue(all(c['cls'].startswith('폼스프레이') for c in cases))  # foam-spray photos are classification-only
 def test_detection_quiz_has_pipe_bolt_photos(self):
  cases=m.load_cases('detection')  # demo_cases/raw/team13_pipe: bolts on pipes
  self.assertTrue(any(c['defect'] for c in cases));self.assertTrue(any(not c['defect'] for c in cases))
  self.assertTrue(all(c['cls'] in ('볼트체결불량','볼트체결양품') and (c['cls']=='볼트체결불량')==c['defect'] for c in cases))
  self.assertEqual(len(m.pick_round(cases)),m.QUIZ_SIZE)
 def test_quiz_truth_prefers_label_quality(self):
  import tempfile,json,os
  with tempfile.TemporaryDirectory() as d:
   os.makedirs(d+'/표면양품');Image.new('RGB',(8,8)).save(d+'/표면양품/a.jpg')
   json.dump({'annotations':[{'attributes':{'quality':'불량품','location':'외벽'}}]},open(d+'/표면양품/a.json','w'))
   open(d+'/samples.csv','w',encoding='utf-8-sig').write('클래스명,이미지 파일,라벨 파일\n표면양품,a.jpg,a.json\n표면양품,missing.jpg,\n')
   cases=m.load_cases('classification',d);self.assertEqual(len(cases),1);self.assertTrue(cases[0]['defect']);self.assertEqual(cases[0]['place'],'외벽')
 def test_round_has_four_mixed_photos(self):
  import random
  cases=[{'id':f'b{i}','defect':True} for i in range(10)]+[{'id':f'g{i}','defect':False} for i in range(10)]
  for seed in range(200):
   ids=m.pick_round(cases,rng=random.Random(seed));self.assertEqual(len(set(ids)),4)
   self.assertTrue(any(i[0]=='b' for i in ids) and any(i[0]=='g' for i in ids))
  self.assertEqual(len(m.pick_round(cases[:3])),3)
  self.assertEqual(sorted(m.pick_round(cases[:2])),['b0','b1'])
 def test_model_defect_verdict(self):
  v=m.model_view('classification',{'classification':{'class':{'name':'폼스프레이불량'},'score':.7,'probabilities':[.1,.1,.7,.1]}});self.assertTrue(v['defect'])
  v=m.model_view('classification',{'classification':{'class':{'name':'표면양품'},'score':.7,'probabilities':[.1,.7,.1,.1]}});self.assertFalse(v['defect'])
  det={'detection':{'detections':[{'class':{'name':'볼트체결양품'},'score':.9,'bbox_xyxy':[0,0,4,4]},{'class':{'name':'볼트체결불량'},'score':.3,'bbox_xyxy':[1,1,2,2]}]}}
  self.assertFalse(m.model_view('detection',det)['defect'])  # defect candidate below the 0.5 display threshold
  det['detection']['detections'][1]['score']=.6;self.assertTrue(m.model_view('detection',det)['defect'])
  self.assertTrue(m.is_defect_class('균열'));self.assertFalse(m.is_defect_class('용접양품'))
 def test_chat_geometry_matches_filtered_overlay_order(self):
  items=[{'class':{'name':name},'score':score,'bbox_xyxy':box} for name,score,box in
         [('균열',.2,[1,1,2,2]),('균열',.7,[2,1,4,3]),('용접양품',.99,[0,0,6,5]),('균열',.9,[5,2,9,7])]]
  summary=m.model_summary('detection',{'detection':{'detections':items}},(12,8),threshold=.5,classes=['균열'])
  self.assertEqual(summary['이미지 크기(px)'],{'너비':12,'높이':8})
  self.assertEqual(summary['전체 후보 수'],4);self.assertEqual(summary['표시 후보 수'],2)
  self.assertEqual([(c['후보 번호'],c['bbox']) for c in summary['후보']],[(1,[2,1,4,3]),(2,[5,2,9,7])])
  self.assertEqual(summary['후보'][0]['점수'],.7)  # keep overlay order, not score order
  empty=m.model_summary('detection',{'detection':{'detections':items}},(12,8),threshold=1)
  self.assertEqual(empty['후보'],[]);self.assertEqual(empty['선택 후보 번호'],'없음')
 def test_chat_selected_candidate_survives_truncation_without_mask(self):
  items=[{'class':{'name':'균열'},'score':.9,'bbox_xyxy':[i,0,i+1,1],
          'mask_rle':{'size':[8,30],'counts':'private-mask'}} for i in range(20)]
  summary=m.model_summary('segmentation',{'segmentation':{'instances':items}},(30,8),threshold=.5,selected=18)
  self.assertEqual(summary['선택 후보 번호'],19);self.assertEqual(summary['후보'][-1]['후보 번호'],19)
  self.assertEqual(summary['생략 후보 수'],5);self.assertEqual(len(summary['후보']),15)
  self.assertNotIn('private-mask',json.dumps(summary))
 def test_chat_classification_has_dimensions_but_no_invented_location(self):
  body={'classification':{'class':{'name':'표면양품'},'score':.8,'probabilities':[.1,.8,.05,.05]}}
  summary=m.model_summary('classification',body,(8,12))
  self.assertEqual(summary['이미지 크기(px)']['높이'],12);self.assertNotIn('후보',summary)
  ctx=m.chat_context(m.MODES['classification'],'결과',**{'모델 결과':summary})
  self.assertIn('사진 파일은 챗봇에 전달되지 않았습니다',ctx['사진 해석 제한'])
 def test_chat_quiz_geometry_fits_context_budget(self):
  import chat_api
  items=[{'class':{'name':'용접블로우홀'},'score':.9876,'bbox_xyxy':[100.123456,200.123456,300.123456,400.123456]} for _ in range(100)]
  summary=m.model_summary('segmentation',{'segmentation':{'instances':items}},(4000,5000),threshold=.5,limit=3)
  ctx=m.chat_context(m.MODES['segmentation'],'직접 판단 실습 · 결과 비교 (제출 후)',**{
   '사진별 결과':[{'사진':f'사진 {i}','정답':'불량 · 용접블로우홀','모델 결과':summary} for i in range(4)]})
  self.assertLess(len(json.dumps(ctx,ensure_ascii=False)),chat_api.MAX_CONTEXT)
  message=chat_api.build_message('2번 후보는 어디인가요?',ctx)
  self.assertIn('bbox:',message);self.assertIn('시각적 근거를 만들지 마세요',message)
 def test_review_correction_choices(self):
  import review as rv
  self.assertNotIn('폼스프레이양품',rv.correction_choices('classification',{'label':'폼스프레이양품','defect':False}))
  self.assertEqual(len(rv.correction_choices('classification',{'label':'표면양품','defect':False})),3)
  self.assertEqual(rv.correction_choices('detection',{'label':'볼트체결불량','defect':True})[0],rv.NO_DEFECT)
  self.assertNotIn(rv.NO_DEFECT,rv.correction_choices('detection',{'label':'후보 없음','defect':False}))
 def test_review_log_csv(self):
  import review as rv
  out=rv.log_csv([{'created':'2026-11-07 10:00:00','mode':'classification','file':'a.jpg','ai':'양품 · 표면양품','score':'99.0%','decision':'거절','mine':'탱크클리닝불량'}])
  self.assertTrue(out.startswith('\ufeff검토 시각'));self.assertIn('탱크클리닝불량',out);self.assertIn('표면 상태 분류',out)
if __name__=='__main__':unittest.main()
