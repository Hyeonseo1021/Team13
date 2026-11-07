import os,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
_T=Path(tempfile.mkdtemp());os.environ['T13_DB']=str(_T/'t.db');os.environ['T13_PHOTOS']=str(_T/'photos')
import accounts as ac

class Accounts(unittest.TestCase):
 def test_signup_login_logout(self):
  tok=ac.signup('홍길동_1234','abcd1234')
  self.assertEqual(ac.user_for_token(tok)['name'],'홍길동_1234')
  self.assertNotIn(tok,ac.DB_PATH.read_bytes().decode('latin-1'))  # only the token hash is stored
  tok2=ac.login('홍길동_1234','abcd1234');self.assertIsNotNone(ac.user_for_token(tok2))
  ac.logout(tok2);self.assertIsNone(ac.user_for_token(tok2))
  self.assertIsNone(ac.user_for_token('nope'))
 def test_password_hashed_and_checked(self):
  h=ac.hash_password('pass1234');self.assertNotIn('pass1234',h)
  self.assertTrue(ac.check_password('pass1234',h));self.assertFalse(ac.check_password('pass12345',h))
 def test_rules(self):
  for name,pw in [('a','abcd1234'),('<script>','abcd1234'),('김철수','short1'),('김철수','12345678'),('김철수','abcdefgh')]:
   with self.assertRaises(ac.AuthError):ac.signup(name,pw)
  ac.signup('이영희','abcd1234')
  with self.assertRaises(ac.AuthError):ac.signup('이영희','other123')   # duplicate name
  with self.assertRaises(ac.AuthError):ac.login('이영희','wrongpw1')
  with self.assertRaises(ac.AuthError):ac.login('없는사람','abcd1234')
 def test_lockout(self):
  ac.signup('Lock Test','abcd1234')
  for _ in range(ac.FAIL_LIMIT):
   with self.assertRaises(ac.AuthError):ac.login('Lock Test','bad')
  with self.assertRaisesRegex(ac.AuthError,'5분'):ac.login('Lock Test','abcd1234')
 def test_expired_session(self):
  tok=ac.signup('만료테스트','abcd1234')
  with ac._connect() as con:con.execute('UPDATE sessions SET expires=?',(time.time()-1,))
  self.assertIsNone(ac.user_for_token(tok))
 def test_reviews_per_user(self):
  a=ac.user_for_token(ac.signup('검토자A','abcd1234'));b=ac.user_for_token(ac.signup('검토자B','abcd1234'))
  rec={'file':'x.jpg','sig':'s','ai':'불량 · 폼스프레이불량','score':'99.0%','decision':'승인','mine':'불량 · 폼스프레이불량'}
  ac.add_review(a['id'],'classification',rec);ac.add_review(a['id'],'detection',dict(rec,decision='거절',mine='양품 (불량 없음)'))
  self.assertEqual(len(ac.reviews_for(a['id'])),2);self.assertEqual(len(ac.reviews_for(a['id'],'classification')),1)
  self.assertEqual(ac.reviews_for(a['id'])[0]['decision'],'거절');self.assertEqual(ac.reviews_for(b['id']),[])
def _jpeg_with_gps(w=3000,h=2000):
 import io;from PIL import Image
 im=Image.new('RGB',(w,h),(90,120,150));ex=Image.Exif();ex[0x010F]='CamCo';ex[0x0110]='GPSPhone'
 b=io.BytesIO();im.save(b,'JPEG',exif=ex);return b.getvalue()

class Photos(unittest.TestCase):
 def setUp(self):
  import hashlib;self.data=_jpeg_with_gps();self.sig=hashlib.sha256(self.data).hexdigest()
  self.rec={'file':'p.jpg','sig':self.sig,'ai':'불량 · 폼스프레이불량','score':'99.0%','decision':'승인','mine':'불량 · 폼스프레이불량'}
 def test_saved_reduced_without_metadata_and_owner_only(self):
  import io;from PIL import Image
  a=ac.user_for_token(ac.signup('사진A','abcd1234'));b=ac.user_for_token(ac.signup('사진B','abcd1234'))
  ac.add_review(a['id'],'classification',self.rec,photo=self.data)
  name=ac.reviews_for(a['id'])[0]['photo'];path=ac.photo_file(a['id'],name)
  self.assertIsNotNone(path);self.assertEqual(oct(path.stat().st_mode&0o777),'0o600')
  im=Image.open(path);self.assertEqual(max(im.size),ac.PHOTO_EDGE);self.assertEqual(len(im.getexif()),0)
  self.assertNotIn(b'CamCo',path.read_bytes())
  self.assertIsNone(ac.photo_file(b['id'],name))                       # another user cannot open it
  self.assertIsNone(ac.photo_file(a['id'],'../'+str(b['id'])+'/x.jpg'))
  ac.add_review(b['id'],'classification',self.rec)                   # no consent -> text only
  self.assertIsNone(ac.reviews_for(b['id'])[0]['photo'])
 def test_same_photo_twice_one_file_and_delete(self):
  a=ac.user_for_token(ac.signup('사진C','abcd1234'))
  ac.add_review(a['id'],'classification',self.rec,photo=self.data);ac.add_review(a['id'],'detection',self.rec,photo=self.data)
  self.assertEqual(len(list((ac.PHOTO_DIR/str(a['id'])).glob('*.jpg'))),1)
  self.assertEqual(ac.delete_photos(a['id']),2)
  self.assertFalse((ac.PHOTO_DIR/str(a['id'])).exists());self.assertEqual(len(ac.reviews_for(a['id'])),2)
 def test_retention(self):
  a=ac.user_for_token(ac.signup('사진D','abcd1234'))
  ac.add_review(a['id'],'classification',self.rec,photo=self.data)
  path=ac.photo_file(a['id'],ac.reviews_for(a['id'])[0]['photo'])
  with ac._connect() as con:con.execute("UPDATE reviews SET created='2020-01-01 00:00:00' WHERE user_id=?",(a['id'],))
  self.assertEqual(ac.purge_old_photos(),1);self.assertFalse(path.exists())
  r=ac.reviews_for(a['id'])[0];self.assertIsNone(r['photo']);self.assertEqual(r['decision'],'승인')
 def test_bad_sig_rejected(self):
  a=ac.user_for_token(ac.signup('사진E','abcd1234'))
  with self.assertRaises(ValueError):ac.add_review(a['id'],'classification',dict(self.rec,sig='../x'),photo=self.data)

if __name__=='__main__':unittest.main()
