import sys,unittest,tempfile,pathlib,json,sqlite3,subprocess
from unittest.mock import patch

import acquisition as a
class AcquisitionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.old=(a.app.ROOT,a.app.MEDIA,a.COMPLETE);a.app.ROOT=self.root;a.app.MEDIA=self.root/'music';a.app.MEDIA.mkdir();a.COMPLETE=self.root/'complete';a.COMPLETE.mkdir()
  with a.app.db() as c:
   c.executescript('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE tracks(id INTEGER PRIMARY KEY,artist TEXT,title TEXT,rating INTEGER,path TEXT,duration REAL,updated INTEGER);CREATE TABLE playlist_pending(playlist_id TEXT,track_id INTEGER);')
   c.execute('INSERT INTO settings VALUES (?,?)',('policy',json.dumps(a.app.POLICY)));c.execute('INSERT INTO tracks VALUES (1,"Thirty Seconds to Mars","The Kill",1,NULL,NULL,0)');c.execute('INSERT INTO playlist_pending VALUES ("one",1)')
  a.init();a.seed();self.track={'id':1,'artist':'Thirty Seconds to Mars','title':'The Kill'}
 def tearDown(self):a.app.ROOT,a.app.MEDIA,a.COMPLETE=self.old;self.tmp.cleanup()
 def test_approved_only(self):
  with a.app.db() as c:c.execute('INSERT INTO tracks VALUES (2,"No","Approval",0,NULL,NULL,0)')
  a.seed()
  with a.app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM acquisition_jobs').fetchone()[0],1)
 def test_revocation(self):
  with a.app.db() as c:c.execute('DELETE FROM playlist_pending')
  a.seed();self.assertFalse(a.eligible(1))
  with a.app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'cancelled')
 def test_no_daily_quota(self):
  for _ in range(55):self.assertTrue(a.reserve(1))
  a.init();self.assertTrue(a.reserve(1))
 def test_prefer_320(self):
  files=[{'filename':'Thirty Seconds to Mars/The Kill.flac','size':900000,'bitRate':1000},{'filename':'Thirty Seconds to Mars/The Kill.mp3','size':900000,'bitRate':320},{'filename':'Thirty Seconds to Mars/The Kill live.mp3','size':900000,'bitRate':320},{'filename':'Other/The Kill.mp3','size':900000,'bitRate':320}]
  r=a.candidates(self.track,[{'username':'private-test','files':files}]);self.assertEqual(len(r),2);self.assertEqual(r[0]['extension'],'.mp3')
 def test_reserve_disk(self):
  with patch.object(a.shutil,'disk_usage',return_value=type('D',(),{'free':99*1024**3})()):self.assertFalse(a.space())
 def test_status_no_peer(self):
  a.update(1,'downloading',source=json.dumps({'username':'secret','filename':'private'}));self.assertNotIn('secret',json.dumps(a.status()))
 def test_lossless_conversion(self):
  source=a.COMPLETE/'The Kill.flac'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=35','-metadata','artist=30 Seconds to Mars','-metadata','title=The Kill','-c:a','flac',str(source)],check=True)
  with patch.object(a.playlists,'call'),patch.object(a.app,'samples'),patch.object(a,'space',return_value=True):target=a.publish(self.track,{'leaf':source.name,'size':source.stat().st_size})
  fmt,audio,tags=a.probe(target);self.assertEqual(audio['codec_name'],'mp3');self.assertEqual(int(audio['bit_rate']),320000);self.assertFalse(source.exists())
 def test_wrong_metadata_retained(self):
  source=a.COMPLETE/'wrong.flac';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=35','-metadata','artist=Wrong','-metadata','title=The Kill',str(source)],check=True)
  with self.assertRaises(ValueError):a.publish(self.track,{'leaf':source.name,'size':source.stat().st_size})
  self.assertTrue(source.exists())
 def test_query_variants(self):
  qs=a.search_queries({'artist':'Bárbara Tinoco','title':'chamada não Atendida'})
  self.assertIn('Barbara Tinoco chamada nao Atendida',qs);self.assertIn('chamada nao Atendida',qs)
  self.assertIn('Crawling',a.search_queries({'artist':'Linkin Park','title':'Crawling'}))
 def test_quality_128_rejected_256_accepted(self):
  with self.assertRaises(a.QualityError):a.check_quality({}, {'codec_name':'aac','bit_rate':'128000'})
  with self.assertRaises(a.QualityError):a.check_quality({}, {'codec_name':'mp3'})
  a.check_quality({}, {'codec_name':'aac','bit_rate':'256000'});a.check_quality({}, {'codec_name':'flac'})
 def test_advertised_128_filtered(self):
  files=[{'filename':'Thirty Seconds to Mars/The Kill.m4a','size':900000,'bitRate':128}]
  self.assertEqual(a.candidates(self.track,[{'username':'test','files':files}]),[])
 def test_failed_peer_excluded_and_retry_limit_increased(self):
  a.update(1,'downloading',source=json.dumps({'username':'test','filename':'file'}));a.reserve(1);a.reserve(1);a.reserve(1);a.error(1,'Failed')
  with a.app.db() as c:
   row=c.execute('SELECT state,excluded_sources,next_at FROM acquisition_jobs').fetchone()
   self.assertEqual(row['state'],'retry');self.assertEqual(json.loads(row['excluded_sources']),[['test','file']]);self.assertGreater(row['next_at'],0)
 def test_fallback_search_and_cleanup(self):
  calls=[]
  def api(path,data=None,method=None):
   calls.append((path,data,method))
   if path=='searches':return {'id':str(len(calls))}
   if path.endswith('/responses'):
    if sum(x[0].endswith('/responses') for x in calls)==1:return []
    return [{'username':'test','files':[{'filename':'Thirty Seconds to Mars/The Kill.mp3','size':900000,'bitRate':320}]}]
   return {}
  with patch.object(a,'api',side_effect=api),patch.object(a.time,'sleep'),patch.object(a,'eligible',return_value=True),patch.object(a,'policy',return_value={**a.app.POLICY,'downloads_enabled':True}):
   self.assertEqual(len(a.search_choices(self.track)),1)
  self.assertEqual(sum(x[2]=='DELETE' for x in calls),2)
 def enable(self):
  with a.app.db() as c:
   cfg=json.loads(c.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0]);cfg['downloads_enabled']=True;c.execute("UPDATE settings SET value=? WHERE key='policy'",(json.dumps(cfg),))
 def test_hourly_search_survives_restart(self):
  self.enable()
  with patch.object(a.time,'time',return_value=10000):self.assertTrue(a.claim_search(1))
  a.update(1,'queued','Interrupted');a.init()
  with patch.object(a.time,'time',return_value=13599):self.assertFalse(a.claim_search(1))
  with patch.object(a.time,'time',return_value=13600):self.assertTrue(a.claim_search(1))
 def test_manual_overrides_interval_without_overlapping(self):
  self.enable()
  with patch.object(a.time,'time',return_value=10000):self.assertTrue(a.claim_search(1))
  with self.assertRaises(ValueError):a.control({'action':'search','id':1})
  a.update(1,'retry',next_at=20000)
  a.control({'action':'search','id':1})
  with patch.object(a.time,'time',return_value=10001):self.assertTrue(a.claim_search(1))
 def test_manual_requires_approval_and_enabled(self):
  with self.assertRaises(ValueError):a.control({'action':'search','id':1})
  self.enable()
  with a.app.db() as c:c.execute('DELETE FROM playlist_pending')
  with self.assertRaises(ValueError):a.control({'action':'search','id':1})
 def test_failure_retries_after_one_hour_even_after_many_attempts(self):
  for _ in range(20):a.reserve(1)
  with patch.object(a.time,'time',return_value=10000):a.error(1,'Failed')
  with a.app.db() as c:
   row=c.execute('SELECT state,next_at FROM acquisition_jobs').fetchone();self.assertEqual(row['state'],'retry');self.assertEqual(row['next_at'],13600)
 def test_alice_deejay_alias_keeps_wrong_artists_out(self):
  track={'artist':'Alice Deejay','title':'Better Off Alone'}
  files=[{'filename':'Alice DJ/Better Off Alone.mp3','size':900000,'bitRate':320},{'filename':'Midwife/Better Off Alone.flac','size':900000,'bitRate':1000}]
  choices=a.candidates(track,[{'username':'test','files':files}]);self.assertEqual(len(choices),1)
  self.assertTrue(a.same_artist('Alice DJ','Alice Deejay'));self.assertFalse(a.same_artist('Midwife','Alice Deejay'))
  self.assertIn('Alice DJ Better Off Alone',a.search_queries(track))
 def add_track(self,tid):
  with a.app.db() as c:
   c.execute('INSERT INTO tracks VALUES (?,"Artist","Song",1,NULL,NULL,0)',(tid,));c.execute('INSERT INTO playlist_pending VALUES ("one",?)',(tid,))
  a.seed()
 def test_search_continues_with_two_downloads(self):
  self.enable();self.add_track(2);self.add_track(3)
  a.update(1,'downloading');a.update(2,'downloading')
  with patch.object(a,'api',return_value={'isLoggedIn':True}),patch.object(a,'start') as start:a.search_tick()
  self.assertEqual(start.call_args[0][0]['id'],3)
 def test_unsearched_tracks_precede_retries_and_manual_has_priority(self):
  self.enable();self.add_track(2)
  a.update(1,'retry',last_search_at=100,next_at=0)
  with patch.object(a,'api',return_value={'isLoggedIn':True}),patch.object(a,'start') as start:a.search_tick()
  self.assertEqual(start.call_args[0][0]['id'],2)
  a.control({'action':'search','id':1})
  with patch.object(a,'api',return_value={'isLoggedIn':True}),patch.object(a,'start') as start:a.search_tick()
  self.assertEqual(start.call_args[0][0]['id'],1)
 def test_search_prepares_without_starting_a_transfer(self):
  self.enable();candidate={'username':'test','filename':'song.mp3','size':900000,'extension':'.mp3','bitrate':320}
  with patch.object(a,'search_choices',return_value=[candidate]),patch.object(a,'api') as api:a.start(self.track)
  api.assert_not_called()
  with a.app.db() as c:
   self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'prepared');self.assertEqual(c.execute('SELECT count(*) FROM acquisition_starts').fetchone()[0],0)
 def test_dispatch_preserves_concurrency(self):
  self.enable();a.update(1,'prepared',source=json.dumps({'found_at':10000}))
  with patch.object(a.time,'time',return_value=10000),patch.object(a,'api',return_value={'isLoggedIn':True}) as api:a.dispatch_ready([{'state':'InProgress'},{'state':'Queued'}])
  self.assertEqual(api.call_count,1)
  with a.app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'prepared')
 def test_transfer_worker_does_not_interrupt_search_worker(self):
  a.update(1,'searching')
  with patch.object(a,'api',return_value=[]),patch.object(a,'dispatch_ready'):a.tick(0)
  with a.app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'searching')
 def test_stalled_provider_releases_slot_after_five_minutes(self):
  self.enable();a.update(1,'downloading',source=json.dumps({'username':'test','filename':'file','requested':9000,'size':900000}))
  transfer={'username':'test','directories':[{'files':[{'id':'transfer','filename':'file','state':'Queued','bytesTransferred':0}]}]};calls=[]
  def api(path,data=None,method=None):
   calls.append((path,method))
   if path=='server':return {'isLoggedIn':True}
   if method=='DELETE':return {}
   return [transfer]
  with patch.object(a,'api',side_effect=api),patch.object(a.time,'time',return_value=10000):a.tick(0)
  self.assertTrue(any(method=='DELETE' for _,method in calls))
  with a.app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'retry')
 def test_aborted_transfer_does_not_hold_slot(self):
  self.enable();a.update(1,'downloading',source=json.dumps({'username':'test','filename':'file','requested':9000,'size':900000}))
  transfer={'username':'test','directories':[{'files':[{'id':'transfer','filename':'file','state':'Completed, Aborted','bytesTransferred':0}]}]}
  def api(path,data=None,method=None):return {'isLoggedIn':True} if path=='server' else [transfer]
  with patch.object(a,'api',side_effect=api),patch.object(a.time,'time',return_value=10000):a.tick(0)
  with a.app.db() as c:self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'retry')
if __name__=='__main__':unittest.main()
