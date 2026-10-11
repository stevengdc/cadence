import pathlib,tempfile,unittest,unittest.mock as mock
import app,playlists,daily,discovery
class DailyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.ROOT;app.ROOT=pathlib.Path(self.tmp.name);app.init();playlists.init()
  with app.db() as c:
   c.execute("INSERT INTO tracks(id,artist,title,track_key,rating) VALUES (1,'Artist','Song','artist|song',1)")
   for lane in app.LANES:c.execute('INSERT INTO playlist_lanes VALUES (?,?)',(lane,'playlist-'+lane))
   c.execute("INSERT INTO daily_candidates(day,lane,track_id,position,reason) VALUES ('2026-10-07','global',1,0,'Top')")
 def tearDown(self):app.ROOT=self.old;self.tmp.cleanup()
 def test_non_style_decision_does_not_change_taste(self):
  with mock.patch.object(playlists,'add',return_value={'ready':False}):playlists.approve({'day':'2026-10-07','lane':'global','id':1,'decision':2})
  with app.db() as c:
   self.assertEqual(c.execute('SELECT rating FROM tracks').fetchone()[0],1)
   self.assertEqual(c.execute('SELECT decision FROM daily_candidates').fetchone()[0],2)
 def test_unavailable_emby_preserves_approval_and_pending(self):
  with mock.patch.object(playlists,'add',side_effect=OSError):result=playlists.approve({'day':'2026-10-07','lane':'global','id':1,'decision':1})
  self.assertTrue(result['sync_pending'])
  with app.db() as c:
   self.assertEqual(c.execute('SELECT decision FROM daily_candidates').fetchone()[0],1)
   self.assertEqual(c.execute('SELECT track_id FROM playlist_pending').fetchone()[0],1)
 def test_daily_overlay_includes_saved_taste(self):
  import accounts
  rows=accounts.overlay_daily(daily.view('all'))['tracks']
  self.assertEqual(rows[0]['rating'],1)
  self.assertEqual(rows[0]['decision'],0)
 def test_no_duplicate_or_reviewed_padding(self):
  pool=[{'artist':'A','title':str(i)} for i in range(4)]+[{'artist':'B','title':'One'},{'artist':'B','title':'One'}]
  rows=daily.choose(pool,{discovery.key('A','0')});self.assertEqual(len(rows),3)
  self.assertEqual(len({discovery.key(t['artist'],t['title']) for t in rows}),3)
 def test_parser_requires_complete_top20(self):
  html=''.join(f'<div class="chart-item"><span class="chart-key"><strong>{i}</strong></span><a class="chart-name"><span>Song {i}</span></a><a class="chart-artist">Artist {i}</a></div>' for i in range(1,21))+'<p>2 October 2026 - 8 October 2026</p>'
  edition,rows=daily.chart_html('uk',html);self.assertEqual(len(rows),20)
  with self.assertRaises(ValueError):daily.chart_html('uk',html.replace('<strong>20</strong>','<strong>21</strong>'))
 def test_playlist_pending_add_is_idempotent(self):
  with mock.patch.object(playlists,'check_playlist',return_value='playlist-style'),mock.patch.object(playlists,'audio_id',return_value=None):
   playlists.add('playlist-style',1);playlists.add('playlist-style',1)
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM playlist_pending').fetchone()[0],1)
 def test_all_days_preserves_decisions_and_pending_filter(self):
  with app.db() as c:
   c.execute("UPDATE daily_candidates SET decision=2 WHERE day='2026-10-07'")
   c.execute("INSERT INTO daily_candidates(day,lane,track_id,position,reason) VALUES ('2026-10-08','global',1,0,'Top')")
  all_days=daily.view('all');self.assertEqual(all_days['day'],'all');self.assertEqual(len(all_days['tracks']),2)
  self.assertEqual({t['decision'] for t in all_days['tracks']},{0,2})
  self.assertEqual(len(daily.view('pending')['tracks']),1)
  self.assertEqual(daily.view('2026-10-07')['tracks'][0]['decision'],2)
if __name__=='__main__':unittest.main()
