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
  self.assertEqual(m.load_cases('detection'),[])  # foam-spray photos are classification-only
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
 def test_review_correction_choices(self):
  import review as rv
  self.assertNotIn('폼스프레이양품',rv.correction_choices('classification',{'label':'폼스프레이양품','defect':False}))
  self.assertEqual(len(rv.correction_choices('classification',{'label':'표면양품','defect':False})),3)
  self.assertEqual(rv.correction_choices('detection',{'label':'볼트체결불량','defect':True})[0],rv.NO_DEFECT)
  self.assertNotIn(rv.NO_DEFECT,rv.correction_choices('detection',{'label':'후보 없음','defect':False}))
 def test_review_log_csv(self):
  import review as rv
  out=rv.log_csv([{'time':'10:00:00','file':'a.jpg','ai':'양품 · 표면양품','score':'99.0%','decision':'거절','mine':'탱크클리닝불량'}])
  self.assertTrue(out.startswith('\ufeff검토 시각'));self.assertIn('탱크클리닝불량',out)
if __name__=='__main__':unittest.main()
