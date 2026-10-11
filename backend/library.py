"""File inventory and reversible removal from the shared collection."""
import concurrent.futures,json,pathlib,secrets,shutil,subprocess,time,fcntl
from contextlib import contextmanager
import app,accounts,playlists,operations
TRASH=pathlib.Path('/data/temporary/library-trash')
def init():
 with app.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS file_details(track_id INTEGER PRIMARY KEY,signature TEXT,data TEXT);
  CREATE TABLE IF NOT EXISTS library_trash(id TEXT PRIMARY KEY,track_id INTEGER,original TEXT,target TEXT,playlists TEXT,created INTEGER,restored INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS activity_log(id INTEGER PRIMARY KEY,created INTEGER,track_id INTEGER,kind TEXT,state TEXT,detail TEXT);''')
def file_path(value):
 p=pathlib.Path(value).resolve();root=app.MEDIA.resolve()
 if not p.is_relative_to(root) or not p.is_file():raise ValueError('Ficheiro indisponível.')
 return p
def metadata(row):
 try:p=file_path(row['path']);stat=p.stat()
 except (OSError,ValueError):return None
 signature=str(stat.st_mtime_ns)+':'+str(stat.st_size)
 with app.db() as c:cached=c.execute('SELECT data FROM file_details WHERE track_id=? AND signature=?',(row['id'],signature)).fetchone()
 if cached:data=json.loads(cached[0])
 else:
  data={'codec':'','bitrate':None,'sample_rate':None,'bits':None,'channels':None,'duration':row.get('duration')}
  try:
   r=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],capture_output=True,text=True,check=True,timeout=20)
   probe=json.loads(r.stdout);audio=next(s for s in probe['streams'] if s.get('codec_type')=='audio');fmt=probe['format']
   data={'codec':audio['codec_name'],'bitrate':round(int(audio.get('bit_rate') or fmt.get('bit_rate') or 0)/1000) or None,'sample_rate':int(audio.get('sample_rate') or 0) or None,'bits':int(audio.get('bits_per_raw_sample') or audio.get('bits_per_sample') or 0) or None,'channels':audio.get('channels'),'duration':float(fmt.get('duration') or audio.get('duration') or 0)}
   with app.db() as c:c.execute('INSERT OR REPLACE INTO file_details VALUES(?,?,?)',(row['id'],signature,json.dumps(data)))
  except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError):data['metadata_error']=True
 target=app.sample_path(row)
 return {k:v for k,v in row.items() if k!='path'}|data|{'file_signature':signature,'filename':p.name,'folder':str(p.parent.relative_to(app.MEDIA.resolve())),'size':stat.st_size,'modified':int(stat.st_mtime),'available':True,'local_preview':bool(target and target.exists())}
def memberships():
 # Administrator token can enumerate playlists across the shared collection.
 all_lists=playlists.call('Items',query={'Recursive':'true','IncludeItemTypes':'Playlist'})['Items']
 by_path={}
 for item in all_lists:
  for entry in playlists.entries(item['Id']):
   path=entry.get('Path')
   if path:by_path.setdefault(path,[]).append({'id':item['Id'],'name':item['Name'],'entry_id':entry['PlaylistItemId']})
 return by_path
def inventory():
 init()
 with app.db() as c:rows=[dict(r) for r in c.execute('SELECT t.id,t.artist,t.title,t.path,t.duration,t.rating,p.deezer_id FROM tracks t LEFT JOIN preview_catalog p ON p.track_id=t.id WHERE t.path IS NOT NULL ORDER BY t.artist,t.title')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=[r for r in pool.map(metadata,rows) if r]
 try:linked=memberships();playlist_ok=True
 except (OSError,ValueError,KeyError):linked={};playlist_ok=False
 for row in files:
  path='/media/music/'+str(pathlib.PurePosixPath(row['folder'])/row['filename'])
  row['playlists']=list({entry['id']:entry for entry in linked.get(path,[])}.values()) if playlist_ok else None
  row['playlist_count']=len(row['playlists']) if playlist_ok else None
 import loudness
 loudness.init()
 with app.db() as c:levels={r['track_id']:dict(r) for r in c.execute('SELECT * FROM loudness')}
 for row in files:
  info=levels.get(row['id']);row['loudness']=json.loads(info['data']) if info and info['signature']==row['file_signature'] else None
 with app.db() as c:trash=[dict(r) for r in c.execute('SELECT x.id,x.track_id,x.created,t.artist,t.title FROM library_trash x JOIN tracks t ON t.id=x.track_id WHERE restored=0 ORDER BY x.created DESC')]
 return {'files':files,'total':len(files),'bytes':sum(r['size'] for r in files),'playlists_ready':playlist_ok,'trash':trash if accounts.admin() else []}
@contextmanager
def exclusive():
 with (app.ROOT/'acquisition.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Há uma importação em curso. Tenta novamente dentro de instantes.')
  try:yield
  finally:fcntl.flock(lock,fcntl.LOCK_UN)
def remove(tid):
 if not accounts.admin():raise PermissionError()
 with exclusive():return _remove(tid)
def _remove(tid):
 if not accounts.admin():raise PermissionError()
 init()
 with app.db() as c:track=c.execute('SELECT * FROM tracks WHERE id=?',(tid,)).fetchone()
 if not track or not track['path']:raise ValueError('Música sem ficheiro.')
 source=file_path(track['path']);emby_path='/media/music/'+str(source.relative_to(app.MEDIA.resolve()))
 linked=memberships().get(emby_path,[])
 # Preserve playlist references for recovery before any external change.
 ident=secrets.token_hex(16);target=TRASH/ident/source.name;target.parent.mkdir(parents=True,exist_ok=False)
 with app.db() as c:c.execute('INSERT INTO library_trash VALUES(?,?,?,?,?,?,0)',(ident,tid,str(source),str(target),json.dumps(linked),int(time.time())))
 try:
  for entry in linked:playlists.call('Playlists/'+playlists.safe_id(entry['id'])+'/Items','DELETE',{'EntryIds':playlists.safe_id(entry['entry_id'])})
  shutil.move(str(source),str(target))
 except Exception:
  # Keep a recoverable record if an external request partly succeeded.
  raise
 with app.db() as c:
  c.execute('UPDATE tracks SET path=NULL WHERE id=?',(tid,));c.execute('DELETE FROM playlist_pending WHERE track_id=?',(tid,))
  if c.execute("SELECT 1 FROM sqlite_master WHERE name='acquisition_jobs'").fetchone():c.execute("UPDATE acquisition_jobs SET state='cancelled',detail='Ficheiro removido da biblioteca',updated=? WHERE track_id=?",(int(time.time()),tid))
  c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'library','removed','Movida para a reciclagem; downloads automáticos cancelados')",(int(time.time()),tid))
  app.event(c,'library_removed',{'id':tid})
 try:playlists.call('Library/Refresh','POST')
 except OSError:pass
 return {'ok':True,'trash_id':ident}
def restore(ident):
 if not accounts.admin():raise PermissionError()
 with exclusive():return _restore(ident)
def _restore(ident):
 if not accounts.admin():raise PermissionError()
 init()
 with app.db() as c:row=c.execute('SELECT * FROM library_trash WHERE id=? AND restored=0',(ident,)).fetchone()
 if not row:raise ValueError('Entrada inexistente na reciclagem.')
 target=pathlib.Path(row['target']).resolve();original=pathlib.Path(row['original']).resolve()
 if not target.is_relative_to(TRASH.resolve()) or not original.is_relative_to(app.MEDIA.resolve()):raise ValueError()
 if target.is_file():
  if original.exists():raise ValueError('Já existe um ficheiro no destino.')
  original.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(target),str(original))
 elif not original.is_file():raise ValueError('Ficheiro de recuperação indisponível.')
 with app.db() as c:
  c.execute('UPDATE tracks SET path=? WHERE id=?',(str(original),row['track_id']))
  c.execute('UPDATE library_trash SET restored=1 WHERE id=?',(ident,))
  for entry in json.loads(row['playlists']):c.execute('INSERT OR IGNORE INTO playlist_pending(playlist_id,track_id) VALUES(?,?)',(entry['id'],row['track_id']))
  if c.execute("SELECT 1 FROM sqlite_master WHERE name='acquisition_jobs'").fetchone():
   c.execute("INSERT INTO acquisition_jobs(track_id,state,detail,updated,progress) VALUES(?,'indexing','Ficheiro restaurado; a atualizar playlists',?,100) ON CONFLICT(track_id) DO UPDATE SET state='indexing',detail=excluded.detail,updated=excluded.updated,progress=100",(row['track_id'],int(time.time())))
  c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'library','restored','Ficheiro restaurado; playlists aguardam reindexação')",(int(time.time()),row['track_id']))
 try:playlists.call('Library/Refresh','POST')
 except OSError:pass
 return {'ok':True}
