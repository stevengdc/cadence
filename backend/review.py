"""Human confirmation for identity/duration mismatches, never for poor audio quality."""
import hashlib,json,pathlib,subprocess,time
import app,accounts,acquisition as a
def retained(tid):
 with app.db() as c:job=c.execute('SELECT state,source FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
 if not job or job['state']!='review' or not job['source']:raise ValueError('Este ficheiro já não está disponível para revisão.')
 source=json.loads(job['source']);path=a.resolve_file(source)
 signature=hashlib.sha256((job['source']+str(path.stat().st_mtime_ns)+str(path.stat().st_size)).encode()).hexdigest()
 return source,path,signature
def details(tid):
 if not accounts.admin():raise PermissionError()
 source,path,signature=retained(tid);track=a.track_for(tid)
 fmt,audio,tags=a.probe(path);reason='';quality_error=''
 try:a.validate(path,track)
 except (ValueError,subprocess.SubprocessError) as e:reason=str(e)
 try:a.check_quality(fmt,audio)
 except a.QualityError as e:quality_error=str(e)
 return {'id':tid,'artist':track['artist'],'title':track['title'],'filename':path.name,'duration':float(fmt.get('duration',0)),
  'expected_duration':track.get('expected_duration'),'codec':audio['codec_name'],'bitrate':round(int(audio.get('bit_rate') or fmt.get('bit_rate') or 0)/1000),
  'file_artist':tags.get('artist',''),'file_title':tags.get('title',''),'reason':reason or 'O ficheiro requer confirmação manual.',
  'can_approve':not quality_error and 30<=float(fmt.get('duration',0))<=1200,'quality_error':quality_error,'fingerprint':signature}
def control(data):
 if not accounts.admin():raise PermissionError()
 tid=int(data['id']);action=data['action']
 if action not in ('approve','reject'):raise ValueError('Ação inválida.')
 info=details(tid)
 if info['fingerprint']!=data.get('fingerprint'):raise ValueError('O ficheiro mudou. Abre novamente a revisão.')
 if action=='approve' and not info['can_approve']:raise ValueError(info['quality_error'] or 'Áudio fora dos limites permitidos.')
 if not a.eligible(tid):raise ValueError('Esta música já não está aprovada para aquisição.')
 with app.db() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT state,source FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()
  if not row or row['state']!='review':raise ValueError('A revisão já foi tratada.')
  source,path,signature=retained(tid)
  if signature!=data.get('fingerprint'):raise ValueError('O ficheiro mudou. Abre novamente a revisão.')
  if action=='approve':
   source['manual_approved']=True
   c.execute("UPDATE acquisition_jobs SET state='converting',source=?,detail='Ficheiro confirmado pelo utilizador; aguarda importação',updated=? WHERE track_id=?",(json.dumps(source),int(time.time()),tid))
  else:
   source.pop('manual_approved',None)
   identity=[source['username'],source['filename']]
   excluded=json.loads(c.execute('SELECT excluded_sources FROM acquisition_jobs WHERE track_id=?',(tid,)).fetchone()[0])
   if identity not in excluded:excluded.append(identity)
   c.execute("UPDATE acquisition_jobs SET state='queued',source=?,excluded_sources=?,next_at=0,manual_requested=1,detail='Ficheiro rejeitado; procurar outra fonte',updated=? WHERE track_id=?",(json.dumps(source),json.dumps(excluded[-64:]),int(time.time()),tid))
  c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'import',?,?)",(int(time.time()),tid,'confirmed' if action=='approve' else 'rejected','Identidade da música confirmada pelo utilizador' if action=='approve' else 'Ficheiro rejeitado na audição; nova fonte pedida'))
 return {'ok':True}
def publish(job):
 source=json.loads(job['source']);original=a.resolve_file(source);track=a.track_for(job['track_id'])
 fmt,audio,tags=a.probe(original);a.check_quality(fmt,audio)
 duration=float(fmt.get('duration',0))
 if not 30<=duration<=1200:raise ValueError('Duração fora dos limites.')
 # The human confirmed this recording. Preserve the audio stream and repair tags only.
 extensions={'mp3':'.mp3','aac':'.m4a','alac':'.m4a','flac':'.flac','opus':'.opus','vorbis':'.ogg','wavpack':'.wv','ape':'.ape'}
 suffix=extensions.get(audio['codec_name'],'.wav' if audio['codec_name'].startswith('pcm_') else None)
 if suffix is None:raise ValueError('Codec não suportado para revisão.')
 folder=a.COMPLETE/'.manual-review';folder.mkdir(exist_ok=True)
 staged=folder/('confirmed-'+str(track['id'])+'-'+str(time.time_ns())+suffix)
 try:
  subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(original),'-map','0:a:0','-vn','-c:a','copy','-metadata','artist='+track['artist'],'-metadata','title='+track['title'],str(staged)],capture_output=True,check=True,timeout=120)
  def audio_hash(path):
   return subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-'],capture_output=True,text=True,check=True,timeout=120).stdout.strip()
  if audio_hash(original)!=audio_hash(staged):raise ValueError('O áudio mudou ao reparar os metadados.')
  track['expected_duration']=duration
  return a.publish(track,{'leaf':staged.name,'size':staged.stat().st_size})
 finally:staged.unlink(missing_ok=True)
