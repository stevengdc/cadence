"""Independent round-robin search and transfer workers; approved-only safe audio import."""
import collections,datetime,fcntl,hashlib,json,os,pathlib,re,secrets,shutil,sqlite3,subprocess,time,urllib.request,urllib.parse,unicodedata
from zoneinfo import ZoneInfo
import app,playlists,discovery
COMPLETE=pathlib.Path('/data/downloads/slskd/complete')
ACTIVE=('searching','downloading','converting','indexing')
TERMINAL=('completed','review','failed','cancelled')
def day():return datetime.datetime.now(ZoneInfo(os.getenv('TZ','UTC'))).date().isoformat()
def init():
 with app.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS activity_log(id INTEGER PRIMARY KEY,created INTEGER,track_id INTEGER,kind TEXT,state TEXT,detail TEXT);
   CREATE TABLE IF NOT EXISTS owned_playlists(playlist_id TEXT PRIMARY KEY,user_id INTEGER);
   CREATE TABLE IF NOT EXISTS acquisition_jobs(track_id INTEGER PRIMARY KEY,state TEXT NOT NULL DEFAULT 'queued',attempts INTEGER DEFAULT 0,next_at INTEGER DEFAULT 0,updated INTEGER DEFAULT 0,detail TEXT DEFAULT '',source TEXT,progress REAL DEFAULT 0,quality TEXT DEFAULT '',created INTEGER DEFAULT(unixepoch()));
   CREATE TABLE IF NOT EXISTS acquisition_starts(id TEXT PRIMARY KEY,day TEXT NOT NULL,track_id INTEGER,created INTEGER DEFAULT(unixepoch()));''')
  for name in ('manual_requested','last_search_at','upgrade'):
   if name not in {r[1] for r in c.execute('PRAGMA table_info(acquisition_jobs)')}:c.execute('ALTER TABLE acquisition_jobs ADD COLUMN '+name+' INTEGER DEFAULT 0')
  if 'excluded_sources' not in {r[1] for r in c.execute('PRAGMA table_info(acquisition_jobs)')}:c.execute("ALTER TABLE acquisition_jobs ADD COLUMN excluded_sources TEXT DEFAULT '[]'")
def api(path,data=None,method=None):
 cfg=json.loads((app.ROOT/'source-connection.json').read_text())
 req=urllib.request.Request(cfg['url']+'/'+path,data=json.dumps(data).encode() if data is not None else None,method=method or ('POST' if data is not None else 'GET'),headers={'X-API-Key':cfg['api_key'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as r:
  body=r.read();return json.loads(body) if body else {}
def policy():
 with app.db() as c:return json.loads(c.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0])
def update(tid,state,detail='',**fields):
 values={'state':state,'detail':detail,'updated':int(time.time()),**fields}
 with app.db() as c:
  previous=c.execute('SELECT state FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
  c.execute('UPDATE acquisition_jobs SET '+','.join(k+'=?' for k in values)+' WHERE track_id=?',(*values.values(),tid))
  if not previous or previous[0]!=state:
   kind='import' if state in ('converting','indexing','completed') else 'download' if state=='downloading' or (previous and previous[0] in ('downloading','converting')) else 'search'
   c.execute('INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,?,?,?)',(int(time.time()),tid,kind,state,detail))
def eligible(tid):
 with app.db() as c:
  if c.execute('SELECT 1 FROM acquisition_jobs j JOIN tracks t ON t.id=j.track_id WHERE j.track_id=? AND j.upgrade=1 AND t.path IS NOT NULL',(tid,)).fetchone():return True
 with app.db() as c:return bool(c.execute('SELECT 1 FROM playlist_pending p JOIN tracks t ON t.id=p.track_id WHERE p.track_id=? AND (t.rating<>-1 OR EXISTS(SELECT 1 FROM owned_playlists o WHERE o.playlist_id=p.playlist_id AND o.user_id<>1))',(tid,)).fetchone())
def seed():
 with app.db() as c:
  c.execute("INSERT OR IGNORE INTO acquisition_jobs(track_id) SELECT DISTINCT t.id FROM tracks t JOIN playlist_pending p ON p.track_id=t.id WHERE t.path IS NULL AND (t.rating<>-1 OR EXISTS(SELECT 1 FROM owned_playlists o WHERE o.playlist_id=p.playlist_id AND o.user_id<>1))")
  # Revoked approvals cannot start a new download. Completed entries remain an audit trail.
  c.execute("UPDATE acquisition_jobs SET state='cancelled',detail='Aprovação removida',updated=? WHERE upgrade=0 AND state IN ('queued','retry','prepared') AND track_id NOT IN (SELECT track_id FROM playlist_pending)",(int(time.time()),))
def artist_key(s):
 k=app.norm(s);return k.replace('thirtysecondstomars','30secondstomars').replace('alicedeejay','alicedj')
def artist_parts(s):
 return [artist_key(x) for x in re.split(r'\s+(?:feat\.?|ft\.?|featuring|&|and|x)\s+|\s*;\s*',s,flags=re.I) if artist_key(x)]
def same_artist(a,b):return sorted(artist_parts(a))==sorted(artist_parts(b))
def search_queries(track):
 artist=track['artist'];title=re.sub(r'\s*\([^)]*\)', '',track['title']).strip()
 plain=lambda x:''.join(c for c in unicodedata.normalize('NFKD',x) if not unicodedata.combining(c))
 clean=lambda x:' '.join(re.findall(r'[^\W_]+',plain(x),re.UNICODE))
 main=re.split(r'\s+(?:feat\.?|ft\.?|featuring|&|and|x)\s+',artist,flags=re.I)[0]
 options=[artist+' '+track['title'],clean(artist+' '+title),clean(main+' '+title)]
 if artist_key(artist)=='alicedj':options.append('Alice DJ '+clean(title))
 if artist_key(artist)=='30secondstomars':options.append('30 Seconds to Mars '+clean(title))
 if len(clean(title))>=4:options.append(clean(title))
 return list(dict.fromkeys(q.strip() for q in options if q.strip()))[:5]

def lossless(audio):return audio['codec_name'] in ('flac','alac','wavpack','ape') or audio['codec_name'].startswith('pcm_')
class QualityError(ValueError):pass
def check_quality(fmt,audio):
 if lossless(audio):return
 if audio['codec_name'] not in ('mp3','aac','opus','vorbis'):raise QualityError('Codec não suportado.')
 bitrate=int(audio.get('bit_rate') or fmt.get('bit_rate') or 0)
 if bitrate<policy().get('min_lossy_kbps',256)*1000*.98:raise QualityError('Qualidade abaixo do mínimo de 256 kbps ou bitrate desconhecido.')

def title_key(s):return discovery.key('',s).split('|',1)[1]
def candidates(track,responses):
 upgrade=bool(track.get('upgrade'))
 result=[];min_rate=policy().get('min_lossy_kbps',256)
 for peer in responses:
  for file in peer.get('files',[]):
   name=file.get('filename','');leaf=name.replace('\\','/').rsplit('/',1)[-1];ext=pathlib.PurePosixPath(leaf).suffix.lower()
   if upgrade and ext!='.flac':continue
   if file.get('isLocked') or ext not in ('.mp3','.flac','.wav','.aiff','.m4a','.ogg','.opus'):continue
   if not 500000<=file.get('size',0)<=200*1024**2:continue
   if artist_parts(track['artist'])[0] not in artist_key(name):continue
   if title_key(track['title']) not in title_key(pathlib.PurePosixPath(leaf).stem):continue
   if re.search(r'\b(live|remix|karaoke|instrumental|cover|tribute|acoustic|nightcore|demo|sped|slowed)\b',leaf,re.I):continue
   length=file.get('length') or 0
   if length and not 30<=length<=1200:continue
   bit=file.get('bitRate') or 0
   if ext not in ('.flac','.wav','.aiff') and bit and bit<min_rate:continue
   pref=0 if ext=='.flac' and policy().get('prefer_lossless') else 1 if policy().get('prefer_lossless') else 0 if ext=='.mp3' and 315<=bit<=325 else 1 if ext in ('.flac','.wav','.aiff') else 2
   score=(pref,not peer.get('hasFreeUploadSlot'),(peer.get('queueLength') or 0),-(peer.get('uploadSpeed') or 0),-min(bit,320))
   result.append((score,{'username':peer['username'],'filename':name,'size':file['size'],'leaf':leaf,'bitrate':bit,'length':length,'extension':ext}))
 return [r[1] for r in sorted(result,key=lambda r:r[0])]
def probe(path):
 r=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,timeout=30,check=True)
 data=json.loads(r.stdout);streams=[s for s in data['streams'] if s['codec_type']=='audio']
 if len(streams)!=1:raise ValueError('Esperado um único fluxo de áudio.')
 tags={k.casefold():v for k,v in data['format'].get('tags',{}).items()}
 return data['format'],streams[0],tags
def validate(path,track):
 fmt,audio,tags=probe(path);duration=float(fmt.get('duration',0))
 if not 30<=duration<=1200:raise ValueError('Duração fora dos limites.')
 if not same_artist(tags.get('artist',''),track['artist']) or title_key(tags.get('title',''))!=title_key(track['title']):raise ValueError('Artista/título dos metadados não corresponde à música aprovada.')
 if re.search(r'\b(live|remix|karaoke|instrumental|cover|tribute|acoustic|nightcore|demo|sped|slowed)\b',tags.get('title',''),re.I):raise ValueError('Versão alternativa: precisa de revisão.')
 if track.get('expected_duration') and abs(duration-track['expected_duration'])>max(10,track['expected_duration']*.05):raise ValueError('Duração não corresponde ao catálogo.')
 check_quality(fmt,audio)
 return fmt,audio,tags

def resolve_file(source):
 root=COMPLETE.resolve();matches=[]
 for p in COMPLETE.rglob('*'):
  if p.name==source['leaf'] and p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root) and p.stat().st_size==source['size']:matches.append(p)
 if len(matches)!=1:raise ValueError('Ficheiro concluído ausente ou ambíguo.')
 return matches[0]
def space(required=0):return shutil.disk_usage(app.MEDIA).free-required>=policy()['reserve_gb']*1024**3

def publish(track,source):
 if track.get('upgrade'):
  import remaster
  return remaster.publish(track,source)
 if not eligible(track['id']):raise ValueError('A aprovação foi removida antes da importação.')
 path=resolve_file(source);fmt,audio,tags=validate(path,track)
 subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',str(path),'-map','0:a:0','-f','null','-'],capture_output=True,check=True,timeout=300)
 is_lossless=lossless(audio)
 supported=audio['codec_name'] in ('mp3','aac','opus','vorbis') or is_lossless
 if not supported:raise ValueError('Codec não suportado.')
 if not space(path.stat().st_size*2):raise ValueError('Reserva de disco atingida.')
 directory=app.MEDIA/'Singles';directory.mkdir(exist_ok=True)
 stem=str(track['id'])+'-'+re.sub(r'[^\w .-]','_',track['artist']+' - '+track['title'])[:160]
 suffix='.mp3' if is_lossless or audio['codec_name']=='mp3' else path.suffix.lower()
 target=directory/(stem+suffix);temp=directory/('.'+stem+'.partial'+suffix)
 if target.exists():
  validate(target,track)
 else:
  try:
   if is_lossless:
    import remaster
    if audio['codec_name']=='flac':remaster.encode(path,temp,track)
    else:subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(path),'-map','0:a:0','-vn','-codec:a','libmp3lame','-b:a','320k','-metadata','artist='+track['artist'],'-metadata','title='+track['title'],str(temp)],capture_output=True,check=True,timeout=300)
   else:
    shutil.copyfile(path,temp)
    if hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(temp.read_bytes()).digest():raise ValueError('Cópia incompleta.')
   import loudness
   loudness_data=loudness.prepare(temp)
   validate(temp,track)
   if not eligible(track['id']):raise ValueError('Aprovação removida durante a importação.')
   temp.chmod(0o644);os.replace(temp,target)
   loudness.record(track['id'],target,loudness_data)
  finally:temp.unlink(missing_ok=True)
 fmt,audio,tags=probe(target);rate=round(int(audio.get('bit_rate') or fmt.get('bit_rate') or 0)/1000)
 quality=('MP3 320 kbps · convertido de fonte sem perdas' if is_lossless else audio['codec_name'].upper()+' '+str(rate)+' kbps · qualidade original')
 with app.db() as c:
  c.execute('UPDATE tracks SET path=?,duration=?,updated=? WHERE id=?',(str(target),float(fmt['duration']),int(time.time()),track['id']))
 update(track['id'],'indexing','A aguardar indexação no Emby',quality=quality,progress=100)
 playlists.call('Library/Refresh','POST')
 app.samples()
 # Delete the downloaded duplicate only after a verified library copy exists; ambiguous files are retained.
 if path.is_file() and path.resolve().is_relative_to(COMPLETE.resolve()):path.unlink()
 return target

def reserve(tid):
 with app.db() as c:
  c.execute('BEGIN IMMEDIATE')
  c.execute('INSERT INTO acquisition_starts(id,day,track_id) VALUES (?,?,?)',(secrets.token_hex(16),day(),tid))
  c.execute('UPDATE acquisition_jobs SET attempts=attempts+1 WHERE track_id=?',(tid,))
 return True

def error(tid,detail,review=False):
 with app.db() as c:
  row=c.execute('SELECT attempts,state,source,excluded_sources FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
  if row and row['source'] and row['state'] in ('downloading','converting'):
   source=json.loads(row['source']);excluded=json.loads(row['excluded_sources']);identity=[source['username'],source['filename']]
   if identity not in excluded:excluded.append(identity)
   c.execute('UPDATE acquisition_jobs SET excluded_sources=? WHERE track_id=?',(json.dumps(excluded[-64:]),tid))
 update(tid,'review' if review else 'retry',detail,manual_requested=0,next_at=int(time.time()+policy().get('retry_minutes',60)*60))

def search_choices(track):
 choices=[];seen=set();queries=search_queries(track)
 with app.db() as c:excluded={tuple(x) for x in json.loads(c.execute('SELECT excluded_sources FROM acquisition_jobs WHERE track_id=?',(track['id'],)).fetchone()[0])}
 for pos,query in enumerate(queries,1):
  if not eligible(track['id']) or not policy()['downloads_enabled']:break
  update(track['id'],'searching',f'A pesquisar variante {pos}/{len(queries)} · '+('apenas FLAC para normalização' if track.get('upgrade') else 'mínimo 256 kbps'))
  search=None
  try:
   search=api('searches',{'searchText':query,'searchTimeout':25000,'responseLimit':300,'fileLimit':8000})
   time.sleep(27)
   for candidate in candidates(track,api('searches/'+search['id']+'/responses')):
    identity=(candidate['username'],candidate['filename'])
    if identity not in seen and identity not in excluded:choices.append(candidate);seen.add(identity)
   if any(x['extension']=='.mp3' and 315<=x['bitrate']<=325 or x['extension'] in ('.flac','.wav','.aiff') for x in choices):break
  finally:
   if search:
    try:api('searches/'+search['id'],method='DELETE')
    except OSError:pass
 return choices

def claim_search(tid):
 if not eligible(tid) or not policy()['downloads_enabled']:return False
 now=int(time.time());interval=policy().get('retry_minutes',60)*60
 with app.db() as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT state,next_at,manual_requested FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
  if not row or row['state'] not in ('queued','retry') or (row['next_at']>now and not row['manual_requested']):return False
  c.execute("UPDATE acquisition_jobs SET state='searching',last_search_at=?,next_at=?,updated=?,detail='A pesquisar MP3 320 kbps ou fonte sem perdas' WHERE track_id=?",(now,now+interval,now,tid))
  c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'search','searching','Pesquisa iniciada: MP3 320 kbps ou fonte sem perdas')",(now,tid))
 return True

def start(track):
 tid=track['id']
 if not claim_search(tid):return
 try:
  choices=search_choices(track)
  if not eligible(tid):update(tid,'cancelled','Aprovação removida');return
  if not policy()['downloads_enabled']:update(tid,'queued','Novos downloads pausados');return
  if not choices:error(tid,'Sem resultado compatível nas variantes pesquisadas; nova pesquisa agendada.');return
  with app.db() as c:row=c.execute('SELECT source,manual_requested FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
  previous=json.loads(row['source']) if row['source'] else {}
  def rank(x):
   quality=0 if x['extension']=='.flac' and policy().get('prefer_lossless') else 1 if policy().get('prefer_lossless') else 0 if x['extension']=='.mp3' and 315<=x['bitrate']<=325 else 1 if x['extension'] in ('.flac','.wav','.aiff') else 2
   return (x['username']==previous.get('username') and x['filename']==previous.get('filename'),quality)
  choices.sort(key=rank)
  candidate=choices[0];candidate['found_at']=int(time.time());candidate['manual']=bool(row['manual_requested'])
  if not eligible(tid):update(tid,'cancelled','Aprovação removida');return
  update(tid,'prepared','Versão encontrada · aguarda vaga para transferir',source=json.dumps(candidate),progress=0,manual_requested=0)
 except (OSError,ValueError,KeyError,TimeoutError):
  with app.db() as c:state=c.execute('SELECT state FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()[0]
  if state!='downloading':error(tid,'Falha na pesquisa; nova tentativa agendada.')

def search_tick(max_new=1):
 init();seed()
 import remaster
 remaster.init()
 if not policy()['downloads_enabled'] or not api('server').get('isLoggedIn'):return
 # This worker holds search.lock; only it recovers its interrupted searches.
 with app.db() as c:
  c.execute("UPDATE acquisition_jobs SET state='queued',manual_requested=0,detail='Pesquisa interrompida; será retomada' WHERE state='searching'")
  rows=[dict(r) for r in c.execute("""SELECT t.*,j.upgrade FROM acquisition_jobs j JOIN tracks t ON t.id=j.track_id
   WHERE j.state IN ('queued','retry') AND j.next_at<=? AND (t.path IS NULL OR (j.upgrade=1 AND EXISTS(SELECT 1 FROM remasters r WHERE r.track_id=t.id AND r.state='queued')))
   ORDER BY j.manual_requested DESC,j.last_search_at,j.created,t.id LIMIT ?""",(int(time.time()),max_new))]
 for track in rows:
  if eligible(track['id']):start(track)

def terminal_transfer(t):return any(w in str(t.get('state','')) for w in ('Completed','Succeeded','Cancelled','Errored','Rejected','TimedOut'))

def dispatch_ready(transfers,max_new=None):
 cfg=policy()
 if not cfg['downloads_enabled'] or not api('server').get('isLoggedIn'):return
 with app.db() as c:
  active=c.execute("SELECT count(*) FROM acquisition_jobs WHERE state IN ('downloading','converting')").fetchone()[0]
  rows=[dict(r) for r in c.execute("SELECT * FROM acquisition_jobs WHERE state='prepared' ORDER BY last_search_at,created,track_id")]
 active=max(active,sum(not terminal_transfer(t) for t in transfers));slots=max(0,cfg['concurrency']-active)
 if max_new is not None:slots=min(slots,max_new)
 rows.sort(key=lambda r:not json.loads(r['source'] or '{}').get('manual'))
 for job in rows:
  tid=job['track_id'];source=json.loads(job['source'] or '{}')
  if not eligible(tid):update(tid,'cancelled','Aprovação removida');continue
  if not source.get('found_at') or time.time()-source['found_at']>3600:
   update(tid,'queued','Resultado expirado; nova pesquisa necessária');continue
  if slots<=0:continue
  if not space(source['size']*2):continue
  if not policy()['downloads_enabled']:break
  source['requested']=source['last_progress_at']=int(time.time());source['last_bytes']=0
  reserve(tid)
  update(tid,'downloading','A aguardar transferência',source=json.dumps(source),progress=0,manual_requested=0)
  try:api('transfers/downloads/'+urllib.parse.quote(source['username'],safe=''),[{'filename':source['filename'],'size':source['size']}])
  except OSError:pass # The request may have reached slskd: reconcile before retrying.
  slots-=1

def flatten(transfers):return [{**f,'username':user['username']} for user in transfers for directory in user.get('directories',[]) for f in directory.get('files',[])]
def track_for(tid):
 with app.db() as c:
  r=c.execute('SELECT t.*,p.deezer_id,coalesce(j.upgrade,0) AS upgrade FROM tracks t LEFT JOIN acquisition_jobs j ON j.track_id=t.id LEFT JOIN preview_catalog p ON p.track_id=t.id WHERE t.id=?',(tid,)).fetchone();track=dict(r)
 if track.get('deezer_id'):
  try:track['expected_duration']=discovery.fetch('track/'+str(track['deezer_id'])).get('duration')
  except (OSError,ValueError,KeyError):pass
 return track

def tick(max_new=None):
 init();seed()
 import remaster
 remaster.init();remaster.local_tick()
 transfers=flatten(api('transfers/downloads'))
 with app.db() as c:jobs=[dict(r) for r in c.execute("SELECT * FROM acquisition_jobs WHERE state IN ('downloading','converting','indexing')")]
 for job in jobs:
  tid=job['track_id'];source=json.loads(job['source']) if job['source'] else None
  with app.db() as c:stored=c.execute('SELECT path FROM tracks WHERE id=?',(tid,)).fetchone()[0]
  if job['state']=='converting' and source and source.get('manual_approved'):
   try:
    import review
    review.publish(job)
   except (ValueError,OSError,subprocess.SubprocessError):error(tid,'Não foi possível importar o ficheiro confirmado; preservado para revisão.',True)
   continue
  if stored and not job['upgrade'] and job['state']!='indexing':
   try:validate(pathlib.Path(stored),track_for(tid));update(tid,'indexing','A aguardar indexação no Emby');job['state']='indexing'
   except (ValueError,OSError,subprocess.SubprocessError):error(tid,'Ficheiro importado requer revisão.',True);continue
  if job['state']=='indexing':
   if job['upgrade']:
    try:remaster.finish(tid)
    except (OSError,ValueError,KeyError):pass
    continue
   try:
    playlists.call('Library/Refresh','POST');playlists.reconcile()
    with app.db() as c:remaining=c.execute('SELECT count(*) FROM playlist_pending WHERE track_id=?',(tid,)).fetchone()[0]
    if not remaining:update(tid,'completed','Disponível no Emby e nas playlists',progress=100)
   except (OSError,ValueError,KeyError):pass
   continue
  if not source: error(tid,'Estado da transferência incompleto.',True);continue
  transfer=next((t for t in transfers if t['username']==source['username'] and t['filename']==source['filename']),None)
  if not eligible(tid):
   if transfer:
    try:api('transfers/downloads/'+urllib.parse.quote(source['username'],safe='')+'/'+transfer['id'],method='DELETE')
    except OSError:continue
   update(tid,'cancelled','Aprovação removida');continue
  if transfer and not terminal_transfer(transfer):
   now=int(time.time());received=int(transfer.get('bytesTransferred') or 0)
   if received>source.get('last_bytes',0):
    source.update(last_bytes=received,last_progress_at=now)
    with app.db() as c:c.execute('UPDATE acquisition_jobs SET source=? WHERE track_id=?',(json.dumps(source),tid))
   if now-source.get('last_progress_at',source.get('requested',job['updated']))>=300:
    try:api('transfers/downloads/'+urllib.parse.quote(source['username'],safe='')+'/'+transfer['id'],method='DELETE')
    except OSError:continue
    error(tid,'Fornecedor sem progresso durante 5 minutos; passa à música seguinte.');continue
  if transfer and not terminal_transfer(transfer) and time.time()-source.get('requested',job['updated'])>7200:
   try:api('transfers/downloads/'+urllib.parse.quote(source['username'],safe='')+'/'+transfer['id'],method='DELETE')
   except OSError:continue
   error(tid,'Tempo de transferência excedido; nova tentativa mais tarde.');continue
  if transfer:
   state=str(transfer.get('state',''));progress=float(transfer.get('percentComplete') or 0)
   if 'Succeeded' in state or (transfer.get('bytesTransferred')==source['size'] and 'Completed' in state):
    try:update(tid,'converting','A validar e preparar o áudio');publish(track_for(tid),source)
    except QualityError:error(tid,'Fonte abaixo de 256 kbps rejeitada; será pesquisada outra versão.')
    except (ValueError,subprocess.SubprocessError):error(tid,'Áudio ou metadados não validados; ficheiro preservado para revisão.',True)
    except OSError:error(tid,'Não foi possível importar; ficheiro preservado para revisão.',True)
   elif terminal_transfer(transfer):error(tid,'Transferência terminada sem sucesso; passa à música seguinte.')
   else:update(tid,'downloading','A descarregar' if 'InProgress' in state else 'Na fila do Soulseek',progress=progress)
  elif time.time()-job['updated']>120:error(tid,'Transferência não confirmada; nova tentativa mais tarde.')
 # Refresh after imports/cancellations so released slots can dispatch cached results.
 dispatch_ready(flatten(api('transfers/downloads')),max_new)

def status():
 init()
 with app.db() as c:
  rows=[dict(r) for r in c.execute('SELECT t.id,t.artist,t.title,j.state,j.detail,j.progress,j.quality,j.upgrade,j.attempts,j.next_at,j.manual_requested,j.last_search_at,j.updated FROM acquisition_jobs j JOIN tracks t ON t.id=j.track_id ORDER BY j.updated DESC,j.created DESC')]
  used=c.execute('SELECT count(*) FROM acquisition_starts WHERE day=?',(day(),)).fetchone()[0]
 return {'enabled':policy()['downloads_enabled'],'policy':policy(),'used_today':used,'jobs':rows,'counts':dict(collections.Counter(r['state'] for r in rows))}
def control(data):
 action=data['action']
 if action in ('pause','resume'):
  if action=='resume' and not api('server').get('isLoggedIn'):raise ValueError('Liga a conta Soulseek primeiro.')
  with app.db() as c:
   cfg=json.loads(c.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0]);cfg.update(mode='assisted',downloads_enabled=action=='resume');c.execute("UPDATE settings SET value=? WHERE key='policy'",(json.dumps(cfg),))
 elif action in ('retry','search'):
  tid=int(data['id'])
  if not policy()['downloads_enabled']:raise ValueError('Retoma os downloads antes de pesquisar.')
  seed()
  if not eligible(tid):raise ValueError('A música já não está aprovada.')
  with app.db() as c:
   cur=c.execute("UPDATE acquisition_jobs SET state='queued',next_at=0,manual_requested=1,detail='Pesquisa manual pedida · prioritária',updated=? WHERE track_id=? AND state IN ('queued','retry','review','failed','prepared')",(int(time.time()),tid))
   if cur.rowcount!=1:raise ValueError('Esta música não está disponível para nova tentativa.')
 else:raise ValueError('Ação inválida.')
 return {'ok':True,'queued':action in ('retry','search')}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--max-new',type=int);p.add_argument('--search-only',action='store_true');args=p.parse_args();init()
 with (app.ROOT/('search.lock' if args.search_only else 'acquisition.lock')).open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit(0)
  try:
   if args.search_only:search_tick(args.max_new or 1)
   else:tick(args.max_new)
  except (OSError,ValueError,KeyError):print('Serviço de aquisição temporariamente indisponível; voltará a tentar.');raise SystemExit(1)
