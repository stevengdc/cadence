import pathlib,tempfile,unittest,json
from unittest.mock import patch
import app,accounts,playlists,library,acquisition,operations
class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=(app.ROOT,app.MEDIA,library.TRASH)
  app.ROOT=pathlib.Path(self.tmp.name)/'state';app.MEDIA=pathlib.Path(self.tmp.name)/'music';app.MEDIA.mkdir();library.TRASH=pathlib.Path(self.tmp.name)/'trash'
  app.init();playlists.init();library.init();acquisition.init();accounts.CURRENT.set(1)
  self.file=app.MEDIA/'song.mp3';self.file.write_bytes(b'audio')
  with app.db() as c:
   c.execute("INSERT INTO tracks(id,artist,title,track_key,path,rating) VALUES(1,'Artist','Song','artist|song',?,2)",(str(self.file),))
   c.execute("INSERT INTO tracks(id,artist,title,track_key) VALUES(2,'Other','Not downloaded','other|missing')")
   c.execute("INSERT INTO playlist_pending VALUES('playlist',1,unixepoch())")
   c.execute("INSERT INTO acquisition_jobs(track_id,state) VALUES(1,'completed')")
 def tearDown(self):app.ROOT,app.MEDIA,library.TRASH=self.old;accounts.CURRENT.set(1);self.tmp.cleanup()
 def test_inventory_downloaded_only(self):
  with patch.object(library,'metadata',side_effect=lambda r:{**{k:v for k,v in r.items() if k!='path'},'size':5,'folder':'.','filename':'song.mp3'}),patch.object(library,'memberships',return_value={'/media/music/song.mp3':[{'id':'playlist','name':'Style'}]}):
   data=library.inventory();self.assertEqual(data['total'],1);self.assertEqual(data['files'][0]['playlist_count'],1)
 def test_reversible_delete_preserves_taste_cancels_reacquisition(self):
  references=[{'id':'playlist','name':'Style','entry_id':'entry'}]
  with patch.object(library,'memberships',return_value={'/media/music/song.mp3':references}),patch.object(playlists,'call'):
   result=library.remove(1);self.assertFalse(self.file.exists())
   with app.db() as c:
    r=c.execute('SELECT path,rating FROM tracks WHERE id=1').fetchone();self.assertEqual(tuple(r),(None,2))
    self.assertEqual(c.execute('SELECT count(*) FROM playlist_pending').fetchone()[0],0)
    self.assertEqual(c.execute('SELECT state FROM acquisition_jobs').fetchone()[0],'cancelled')
   library.restore(result['trash_id']);self.assertTrue(self.file.exists())
   with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM playlist_pending').fetchone()[0],1)
 def test_nonadmin_cannot_delete(self):
  with patch.object(accounts,'admin',return_value=False),self.assertRaises(PermissionError):library.remove(1)
  self.assertTrue(self.file.exists())
 def test_outside_music_never_removed(self):
  outside=app.ROOT/'private.mp3';outside.write_bytes(b'private')
  with app.db() as c:c.execute('UPDATE tracks SET path=? WHERE id=1',(str(outside),))
  with self.assertRaises(ValueError):library.remove(1)
  self.assertTrue(outside.exists())
 def test_activity_logs_state_changes_not_progress(self):
  acquisition.update(1,'downloading','Transferência iniciada');acquisition.update(1,'downloading','Transferência em curso',progress=20)
  acquisition.update(1,'completed','Importada')
  data=operations.activity({'kind':['download']});self.assertEqual(data['total'],1)
  self.assertEqual(data['entries'][0]['state'],'downloading')
  data=operations.activity({'kind':['import']});self.assertEqual(data['total'],1)
if __name__=='__main__':unittest.main()
