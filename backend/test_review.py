import pathlib,tempfile,unittest,json,subprocess
from unittest.mock import patch
import app,accounts,playlists,acquisition as a,review
class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=(app.ROOT,app.MEDIA,a.COMPLETE)
  app.ROOT=pathlib.Path(self.tmp.name)/'state';app.MEDIA=pathlib.Path(self.tmp.name)/'music';app.MEDIA.mkdir();a.COMPLETE=pathlib.Path(self.tmp.name)/'complete';a.COMPLETE.mkdir()
  app.init();playlists.init();a.init();accounts.CURRENT.set(1)
  self.path=a.COMPLETE/'Artist - Song.mp3'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=35','-c:a','libmp3lame','-b:a','320k',str(self.path)],check=True)
  self.source={'username':'test-private','filename':'Artist/Song.mp3','leaf':self.path.name,'size':self.path.stat().st_size}
  with app.db() as c:
   c.execute("INSERT INTO tracks(id,artist,title,track_key,rating) VALUES(1,'Artist','Song','artist|song',1)")
   c.execute("INSERT INTO playlist_pending(playlist_id,track_id) VALUES('playlist',1)")
   c.execute("INSERT INTO acquisition_jobs(track_id,state,source) VALUES(1,'review',?)",(json.dumps(self.source),))
 def tearDown(self):app.ROOT,app.MEDIA,a.COMPLETE=self.old;accounts.CURRENT.set(1);self.tmp.cleanup()
 def test_local_audio_details_and_approval_queue(self):
  info=review.details(1);self.assertTrue(info['can_approve']);self.assertEqual(info['bitrate'],320)
  self.assertEqual(info['file_artist'],'');self.assertNotIn('test-private',json.dumps(info))
  review.control({'id':1,'action':'approve','fingerprint':info['fingerprint']})
  with app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'converting')
  self.assertTrue(self.path.exists())
 def test_reject_requests_another_source_without_deleting(self):
  info=review.details(1);review.control({'id':1,'action':'reject','fingerprint':info['fingerprint']})
  with app.db() as c:
   row=c.execute('SELECT state,manual_requested,excluded_sources FROM acquisition_jobs').fetchone()
   self.assertEqual((row[0],row[1]),('queued',1));self.assertEqual(len(json.loads(row[2])),1)
  self.assertTrue(self.path.exists())
 def test_stale_and_nonadmin_denied(self):
  with self.assertRaises(ValueError):review.control({'id':1,'action':'approve','fingerprint':'old'})
  with patch.object(accounts,'admin',return_value=False),self.assertRaises(PermissionError):review.details(1)
 def test_128_cannot_be_manually_approved(self):
  self.path.unlink();subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=35','-c:a','libmp3lame','-b:a','128k',str(self.path)],check=True)
  self.source['size']=self.path.stat().st_size
  with app.db() as c:c.execute('UPDATE acquisition_jobs SET source=?',(json.dumps(self.source),))
  info=review.details(1);self.assertFalse(info['can_approve'])
  with self.assertRaises(ValueError):review.control({'id':1,'action':'approve','fingerprint':info['fingerprint']})
 def test_confirmed_import_repairs_tags_without_reencoding(self):
  info=review.details(1);review.control({'id':1,'action':'approve','fingerprint':info['fingerprint']})
  with app.db() as c:job=dict(c.execute('SELECT * FROM acquisition_jobs').fetchone())
  with patch.object(playlists,'call'),patch.object(app,'samples'),patch.object(a,'space',return_value=True):target=review.publish(job)
  fmt,audio,tags=a.probe(target);self.assertEqual(tags['artist'],'Artist');self.assertEqual(tags['title'],'Song');self.assertEqual(int(audio['bit_rate']),320000)
  self.assertTrue(self.path.exists())
if __name__=='__main__':unittest.main()
