import pathlib,tempfile,unittest
from unittest.mock import patch
import app,accounts,redistribution as r
class SharingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.ROOT;app.ROOT=pathlib.Path(self.tmp.name);app.init();r.init()
  self.rows=[{'id':1,'artist':'A','title':'T','filename':'a.mp3','size':5,'modified':1,'codec':'mp3','bitrate':320,'rating':1},{'id':2,'artist':'B','title':'U','filename':'b.mp3','size':5,'modified':1,'codec':'mp3','bitrate':128,'rating':1}]
  self.mock=patch.object(r.library,'inventory',return_value={'files':self.rows});self.mock.start();self.admin=patch.object(accounts,'admin',return_value=True);self.admin.start()
 def tearDown(self):self.mock.stop();self.admin.stop();app.ROOT=self.old;self.tmp.cleanup()
 def test_default_bulk_revoke_audit(self):
  self.assertFalse(any(x['authorized'] for x in r.inventory()['files']))
  r.control({'ids':[1],'authorized':True});self.assertTrue(r.inventory()['files'][0]['authorized'])
  r.control({'ids':[1,2],'authorized':False});self.assertFalse(any(x['authorized'] for x in r.inventory()['files']))
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM redistribution').fetchone()[0],2)
 def test_atomic_validation(self):
  with self.assertRaises(ValueError):r.control({'ids':[1,2],'authorized':True})
  self.assertFalse(r.inventory()['files'][0]['authorized'])
 def test_file_changed_invalidates_grant(self):
  r.control({'ids':[1],'authorized':True});self.rows[0]['size']=7
  self.assertFalse(r.inventory()['files'][0]['authorized'])
 def test_export_and_revoke(self):
  source=app.ROOT/'music'/'a.mp3';source.parent.mkdir();source.write_bytes(b'test audio')
  with app.db() as c:c.execute("INSERT INTO tracks(id,artist,title,track_key,path) VALUES(1,'A','T','a|t',?)",(str(source),))
  with patch.object(app,'MEDIA',source.parent),patch.object(r,'EXPORT',app.ROOT/'export'),patch.object(r.acquisition,'api') as call:
   self.assertEqual(r.sync()['exported'],0)
   r.control({'ids':[1],'authorized':True});self.assertEqual(r.sync()['exported'],1)
   self.assertEqual(next(r.EXPORT.iterdir()).read_bytes(),b'test audio');call.assert_called_with('shares',method='PUT')
   r.control({'ids':[1],'authorized':False});self.assertEqual(r.sync()['exported'],0);self.assertEqual(list(r.EXPORT.iterdir()),[])
 def test_nonadmin(self):
  with patch.object(accounts,'admin',return_value=False),self.assertRaises(PermissionError):r.control({'ids':[1],'authorized':True})
if __name__=='__main__':unittest.main()
