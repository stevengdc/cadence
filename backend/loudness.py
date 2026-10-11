"""Measured per-track ReplayGain. Audio packets are verified unchanged."""
import hashlib,json,math,os,pathlib,re,shutil,subprocess,time
import app
TARGET=-18.0
PEAK=-1.0
VERSION=1

def init():
 with app.db() as c:c.execute('CREATE TABLE IF NOT EXISTS loudness(track_id INTEGER PRIMARY KEY,signature TEXT,data TEXT,updated INTEGER)')
def signature(path):
 stat=path.stat();return str(stat.st_mtime_ns)+':'+str(stat.st_size)
def measure(path):
 proc=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-v','info','-i',str(path),'-map','0:a:0','-af','loudnorm=I=-18:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True,timeout=300)
 matches=re.findall(r'\{\s*"input_i".*?\}',proc.stderr,re.S)
 if not matches:raise ValueError('Não foi possível medir o loudness.')
 data=json.loads(matches[-1]);integrated=float(data['input_i']);peak=float(data['input_tp'])
 if not math.isfinite(integrated) or not math.isfinite(peak):raise ValueError('Áudio silencioso ou loudness inválido; requer revisão.')
 wanted=TARGET-integrated;gain=math.floor(min(wanted,PEAK-peak)*100)/100
 return {'lufs':integrated,'true_peak':peak,'gain_db':gain,'target_lufs':TARGET,'result_lufs':round(integrated+gain,2),'peak_limited':gain<wanted-.02,'version':VERSION}
def stream_hash(path):
 return subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-'],capture_output=True,text=True,check=True,timeout=120).stdout.strip()
def tag(path,data):
 import mutagen
 from mutagen.id3 import TXXX
 from mutagen.mp3 import MP3
 from mutagen.mp4 import MP4,MP4FreeForm
 audio=mutagen.File(path)
 if audio is None:raise ValueError('Formato sem suporte a ReplayGain.')
 if audio.tags is None:audio.add_tags()
 values={'REPLAYGAIN_TRACK_GAIN':f"{data['gain_db']:+.2f} dB",'REPLAYGAIN_TRACK_PEAK':f"{10**(data['true_peak']/20):.8f}",'REPLAYGAIN_REFERENCE_LOUDNESS':'89.0 dB'}
 if isinstance(audio,MP3):
  for frame in list(audio.tags.values()):
   if isinstance(frame,TXXX) and frame.desc.upper().startswith(('REPLAYGAIN_','R128_')):audio.tags.delall(frame.HashKey)
  for key,value in values.items():audio.tags.add(TXXX(encoding=3,desc=key,text=[value]))
 elif isinstance(audio,MP4):
  for key in list(audio.tags.keys()):
   if 'replaygain_' in key.lower() or 'r128_' in key.lower():del audio.tags[key]
  for key,value in values.items():audio.tags['----:com.apple.iTunes:'+key]=[MP4FreeForm(value.encode())]
 else:
  for key in list(audio.tags.keys()):
   if key.upper().startswith(('REPLAYGAIN_','R128_')):del audio.tags[key]
  for key,value in values.items():audio.tags[key]=[value]
 audio.save()
def prepare(path):
 data=measure(path);before=stream_hash(path);tag(path,data)
 if stream_hash(path)!=before:raise ValueError('O áudio mudou ao gravar ReplayGain.')
 return data
def record(tid,path,data):
 init()
 with app.db() as c:c.execute('INSERT OR REPLACE INTO loudness VALUES(?,?,?,?)',(tid,signature(path),json.dumps(data),int(time.time())))
def backfill(tid):
 import library
 with library.exclusive():
  init()
  with app.db() as c:
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='remasters'").fetchone() and c.execute("SELECT 1 FROM remasters WHERE track_id=? AND state<>'completed'",(tid,)).fetchone():return False
  with app.db() as c:
   row=c.execute('SELECT * FROM tracks WHERE id=? AND path IS NOT NULL',(tid,)).fetchone();cached=c.execute('SELECT signature,data FROM loudness WHERE track_id=?',(tid,)).fetchone()
  if not row:return False
  path=library.file_path(row['path']);sig=signature(path)
  if cached and cached['signature']==sig and json.loads(cached['data']).get('version')==VERSION:return False
  before={'filename':path.name,'size':path.stat().st_size,'file_signature':sig,'modified':int(path.stat().st_mtime)}
  backups=app.ROOT/'loudness-originals';backups.mkdir(exist_ok=True)
  backup=backups/(str(tid)+'-'+hashlib.sha256(sig.encode()).hexdigest()[:12]+path.suffix)
  if not backup.exists():shutil.copy2(path,backup)
  temp=path.parent/('.'+path.stem+'.replaygain'+path.suffix)
  try:
   shutil.copy2(path,temp);data=prepare(temp)
   if signature(path)!=sig:raise ValueError('O ficheiro mudou durante a análise.')
   os.replace(temp,path);record(tid,path,data)
   # A verified metadata-only edit does not change an existing redistribution consent.
   import redistribution
   with app.db() as c:
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='redistribution'").fetchone():
     new=before|{'size':path.stat().st_size,'file_signature':signature(path),'modified':int(path.stat().st_mtime)}
     c.execute('UPDATE redistribution SET signature=? WHERE track_id=? AND signature=?',(redistribution.signature(new),tid,redistribution.signature(before)))
    c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'library','loudness',?)",(int(time.time()),tid,f"ReplayGain: {data['lufs']:.1f} LUFS; ajuste {data['gain_db']:+.2f} dB; áudio preservado"))
   return True
  finally:temp.unlink(missing_ok=True)
def main():
 init()
 with app.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM tracks WHERE path IS NOT NULL')]
 progress={'total':len(ids),'processed':0,'updated':0,'errors':0,'started':int(time.time())};state=app.ROOT/'loudness-progress.json';state.write_text(json.dumps(progress))
 for tid in ids:
  try:
   if backfill(tid):progress['updated']+=1
  except (OSError,ValueError,subprocess.SubprocessError) as error:progress['errors']+=1;progress['last_error']=str(error);progress['last_error_track']=tid
  progress['processed']+=1;state.write_text(json.dumps(progress));time.sleep(.2)
 progress['finished']=int(time.time());state.write_text(json.dumps(progress))
 import playlists
 playlists.call('Library/Refresh','POST');print(json.dumps(progress))
if __name__=='__main__':main()
