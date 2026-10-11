import json,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
import acquisition as a,remaster as r,loudness

class RemasterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.old=(a.app.ROOT,a.app.MEDIA,a.COMPLETE)
  a.app.ROOT=self.root;a.app.MEDIA=self.root/'music';a.app.MEDIA.mkdir();a.COMPLETE=self.root/'complete';a.COMPLETE.mkdir()
  with a.app.db() as c:
   c.executescript('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE tracks(id INTEGER PRIMARY KEY,artist TEXT,title TEXT,rating INTEGER,path TEXT,duration REAL,updated INTEGER);CREATE TABLE playlist_pending(playlist_id TEXT,track_id INTEGER);')
   c.execute('INSERT INTO settings VALUES(?,?)',('policy',json.dumps(a.app.POLICY)))
  a.init();r.init();self.track={'id':1,'artist':'Artist','title':'Song','upgrade':1}
 def tearDown(self):a.app.ROOT,a.app.MEDIA,a.COMPLETE=self.old;self.tmp.cleanup()
 def make(self,path,codec='flac'):
  args=['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=35','-metadata','artist=Artist','-metadata','title=Song','-c:a',codec]
  if codec=='libmp3lame':args+=['-b:a','320k']
  subprocess.run(args+[str(path)],check=True)
 def seed_track(self,old):
  with a.app.db() as c:c.execute('INSERT INTO tracks VALUES(1,"Artist","Song",1,?,35,0)',(str(old),))
  r.seed()
 def test_strict_flac_candidates(self):
  files=[{'filename':'Artist/Song.mp3','size':900000,'bitRate':320},{'filename':'Artist/Song.flac','size':900000}]
  result=a.candidates(self.track,[{'username':'test','files':files}])
  self.assertEqual([x['extension'] for x in result],['.flac'])
 def test_normalizes_lossless_before_single_mp3_encode(self):
  source=self.root/'source.flac';target=self.root/'out.mp3';self.make(source)
  before=loudness.stream_hash(source);data=r.encode(source,target,self.track)
  self.assertEqual(loudness.stream_hash(source),before)
  self.assertLessEqual(data['true_peak'],-1);self.assertAlmostEqual(data['lufs'],-18,delta=.5)
  self.assertEqual(a.probe(target)[1]['bit_rate'],'320000');self.assertTrue(data['normalized'])
 def test_mp3_source_rejected(self):
  source=self.root/'source.mp3';self.make(source,'libmp3lame')
  with self.assertRaises(ValueError):r.encode(source,self.root/'out.mp3',self.track)
 def test_replacement_preserves_original_and_playlist_until_indexed(self):
  old=a.app.MEDIA/'original.flac';self.make(old);self.seed_track(old);before=loudness.stream_hash(old)
  with patch('library.memberships',return_value={'/media/music/original.flac':[{'id':'p','entry_id':'e','name':'Playlist'}]}),patch.object(a,'space',return_value=True),patch.object(r.playlists,'call'):
   target=r.publish(self.track,{'local_path':str(old)})
   with patch.object(r.playlists,'audio_id',return_value=None):self.assertFalse(r.finish(1))
  self.assertTrue(old.exists());self.assertTrue(target.exists())
  with a.app.db() as c:row=c.execute('SELECT * FROM remasters').fetchone()
  self.assertEqual(loudness.stream_hash(pathlib.Path(row['backup'])),before)
  calls=[]
  def entries(pid):return [{'Id':'new','PlaylistItemId':'n'},{'Id':'old','PlaylistItemId':'e'}]
  with patch.object(r.playlists,'audio_id',return_value='new'),patch.object(r.playlists,'entries',side_effect=entries),patch.object(r.playlists,'call',side_effect=lambda *args,**kwargs:calls.append(args)):
   self.assertTrue(r.finish(1))
  self.assertFalse(old.exists());self.assertTrue(pathlib.Path(row['backup']).exists());self.assertTrue(target.exists())
  self.assertIn(('Playlists/p/Items','DELETE',{'EntryIds':'e'}),calls)
 def test_changed_original_is_never_overwritten(self):
  old=a.app.MEDIA/'old.mp3';self.make(old,'libmp3lame');self.seed_track(old)
  old.write_bytes(old.read_bytes()+b'changed')
  with self.assertRaises(ValueError):r.publish(self.track,{'leaf':'unavailable','size':1})

if __name__=='__main__':unittest.main()
