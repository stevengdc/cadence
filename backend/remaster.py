"""Recoverable FLAC-to-normalized-MP3 library replacement."""
import json,math,os,pathlib,shutil,subprocess,time
import app,loudness,playlists

def init():
 with app.db() as c:c.execute('CREATE TABLE IF NOT EXISTS remasters(track_id INTEGER PRIMARY KEY,original TEXT,signature TEXT,state TEXT,links TEXT,backup TEXT,target TEXT,detail TEXT DEFAULT "")')

def encode(source,target,track):
 import acquisition as a
 fmt,audio,tags=a.probe(source)
 if audio['codec_name']!='flac':raise ValueError('A substituição exige uma fonte FLAC real.')
 subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',str(source),'-map','0:a:0','-f','null','-'],capture_output=True,check=True,timeout=300)
 original=loudness.measure(source)
 gain=math.floor(min(loudness.TARGET-original['lufs'],-2-original['true_peak'])*100)/100
 for _ in range(3):
  subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-map','0:a:0','-map','0:v?','-map_metadata','0','-af',f'volume={gain}dB','-ar','44100','-codec:a','libmp3lame','-b:a','320k','-codec:v','copy','-id3v2_version','3','-metadata','artist='+track['artist'],'-metadata','title='+track['title'],str(target)],capture_output=True,check=True,timeout=300)
  data=loudness.measure(target)
  if data['true_peak']<=-1:
   if data['lufs']>loudness.TARGET+.5:raise ValueError('Volume final acima da referência.')
   a.validate(target,track)
   data.update(normalized=True,source_lufs=original['lufs'],applied_gain_db=gain)
   loudness.tag(target,data)
   return data
  gain-=data['true_peak']+1.2
 raise ValueError('Não foi possível respeitar o limite de pico do MP3.')

def publish(track,source):
 import acquisition as a,library
 init()
 with app.db() as c:row=dict(c.execute('SELECT * FROM remasters WHERE track_id=?',(track['id'],)).fetchone())
 old=library.file_path(row['original'])
 if loudness.signature(old)!=row['signature']:raise ValueError('O original mudou; substituição suspensa para revisão.')
 path=library.file_path(source['local_path']) if source.get('local_path') else a.resolve_file(source)
 if not source.get('local_path'):a.validate(path,track)
 if not a.space(path.stat().st_size*3+old.stat().st_size):raise ValueError('Reserva de disco atingida.')
 root=app.ROOT/'remaster-originals'/str(track['id']);root.mkdir(parents=True,exist_ok=True)
 backup=root/old.name
 if not backup.exists():shutil.copy2(old,backup)
 target=old if old.suffix.lower()=='.mp3' else app.MEDIA/'Singles'/(str(track['id'])+'-normalizado.mp3')
 target.parent.mkdir(exist_ok=True)
 temp=target.parent/('.'+target.stem+'.remaster.mp3')
 emby_old='/media/music/'+str(old.relative_to(app.MEDIA.resolve()))
 links=library.memberships().get(emby_old,[])
 try:
  data=encode(path,temp,track)
  if loudness.signature(old)!=row['signature']:raise ValueError('O original mudou durante a conversão.')
  if not source.get('local_path'):
   saved=root/'source.flac'
   if not saved.exists():shutil.copy2(path,saved)
  with app.db() as c:c.execute('UPDATE remasters SET state="publishing",links=?,backup=?,target=? WHERE track_id=?',(json.dumps(links),str(backup),str(target),track['id']))
  temp.chmod(0o644);os.replace(temp,target)
  loudness.record(track['id'],target,data)
  with app.db() as c:
   c.execute('UPDATE tracks SET path=?,duration=?,updated=? WHERE id=?',(str(target),a.probe(target)[0]['duration'],int(time.time()),track['id']))
   c.execute('UPDATE remasters SET state="published" WHERE track_id=?',(track['id'],))
  a.update(track['id'],'indexing','MP3 320 normalizado; a preservar as playlists',quality='MP3 320 kbps · FLAC · áudio normalizado',progress=100)
  try:playlists.call('Library/Refresh','POST')
  except OSError:pass # Published safely; the indexing worker will retry.
  return target
 finally:temp.unlink(missing_ok=True)

def finish(tid):
 import acquisition as a,library
 with app.db() as c:row=c.execute('SELECT * FROM remasters WHERE track_id=?',(tid,)).fetchone()
 if not row or row['state'] not in ('published','publishing'):return False
 target=pathlib.Path(row['target']);old=pathlib.Path(row['original'])
 # Recovery of a process interrupted between file replacement and database commit.
 with app.db() as c:track=dict(c.execute('SELECT * FROM tracks WHERE id=?',(tid,)).fetchone())
 if track['path']!=str(target):
  raise ValueError('Publicação interrompida; original preservado para revisão.')
 new_id=playlists.audio_id(track)
 if not new_id:return False
 for link in json.loads(row['links']):
  entries=playlists.entries(link['id'])
  if new_id not in {e['Id'] for e in entries}:playlists.call('Playlists/'+link['id']+'/Items','POST',{'Ids':new_id})
  if old!=target:
   entries=playlists.entries(link['id'])
   if new_id not in {e['Id'] for e in entries}:return False
   if link['entry_id'] in {e['PlaylistItemId'] for e in entries}:playlists.call('Playlists/'+link['id']+'/Items','DELETE',{'EntryIds':link['entry_id']})
 if old!=target and old.exists():
  if loudness.signature(old)!=row['signature']:raise ValueError('Original alterado; não foi retirado da biblioteca.')
  # Already backed up; retain the original by moving, never delete it.
  shutil.move(str(old),str(pathlib.Path(row['backup']).with_name('retired-'+old.name)))
 with app.db() as c:
  c.execute('UPDATE remasters SET state="completed" WHERE track_id=?',(tid,))
  c.execute('UPDATE acquisition_jobs SET upgrade=0 WHERE track_id=?',(tid,))
 a.update(tid,'completed','Substituído por MP3 320 normalizado de FLAC; original guardado',progress=100)
 try:playlists.call('Library/Refresh','POST')
 except OSError:pass
 return True

def local_tick():
 import acquisition as a
 with app.db() as c:
  c.execute("UPDATE remasters SET state='cancelled' WHERE state='local' AND track_id IN (SELECT id FROM tracks WHERE path IS NULL)")
  row=c.execute('SELECT t.* FROM remasters r JOIN tracks t ON t.id=r.track_id WHERE r.state="local" AND t.path=r.original LIMIT 1').fetchone()
 if not row:return
 track=dict(row)
 try:
  a.update(track['id'],'converting','A normalizar a fonte FLAC já existente')
  publish(track,{'local_path':track['path']})
 except (OSError,ValueError,subprocess.SubprocessError) as e:
  with app.db() as c:c.execute('UPDATE remasters SET state="review",detail=? WHERE track_id=?',(str(e),track['id']))
  a.error(track['id'],'Conversão local suspensa; original preservado para revisão.',True)

def seed():
 import acquisition as a,library
 a.init();init()
 with app.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM tracks WHERE path IS NOT NULL')]
 counts={'local':0,'queued':0,'skipped':0}
 for track in rows:
  try:path=library.file_path(track['path'])
  except ValueError:counts['skipped']+=1;continue
  with app.db() as c:
   if c.execute('SELECT 1 FROM remasters WHERE track_id=?',(track['id'],)).fetchone():continue
   job=c.execute('SELECT state FROM acquisition_jobs WHERE track_id=?',(track['id'],)).fetchone()
   if job and job['state'] in ('searching','prepared','downloading','converting','indexing'):counts['skipped']+=1;continue
   state='local' if a.probe(path)[1]['codec_name']=='flac' else 'queued'
   c.execute('INSERT INTO remasters(track_id,original,signature,state,links) VALUES(?,?,?,?,"[]")',(track['id'],str(path),loudness.signature(path),state))
   c.execute('INSERT INTO acquisition_jobs(track_id,state,upgrade,detail) VALUES(?,?,1,?) ON CONFLICT(track_id) DO UPDATE SET state=excluded.state,upgrade=1,next_at=0,source=NULL,progress=0,excluded_sources="[]",detail=excluded.detail', (track['id'],'queued','Migração: FLAC → MP3 320 normalizado'))
   counts[state]+=1
 print(json.dumps(counts))

if __name__=='__main__':seed()
