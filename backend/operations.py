"""Bounded operations API: schedules, tasks and service health."""
import os,datetime,json,pathlib,re,subprocess,urllib.request
import app,accounts
DEFAULTS={
 'daily':{'name':'Propostas diárias','kind':'calendar','time':'07:00','enabled':True,'description':'Até 10 propostas por lista. Tops mundial, UK e Portugal.'},
 'search':{'name':'Percorrer músicas aprovadas','kind':'interval','seconds':5,'enabled':True,'description':'Pesquisa uma música de cada vez, independentemente dos downloads.'},
 'acquisition':{'name':'Transferências e importação','kind':'interval','seconds':60,'enabled':True,'description':'Valida qualidade, importa para o Emby e atualiza playlists.'},
 'backup':{'name':'Backup local do perfil','kind':'calendar','time':'03:15','enabled':True,'description':'Cópia local de segurança. O backup externo continua pendente.'}}
def emby(path,method='GET',body=None):
 cfg=json.loads((app.ROOT/'emby-connection.json').read_text())
 req=urllib.request.Request(cfg['url']+'/'+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'X-Emby-Token':cfg['token'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:
  raw=r.read();return json.loads(raw) if raw else {}
def schedules():
 try:config=json.loads((app.ROOT/'schedules.json').read_text())
 except (OSError,ValueError):config={}
 rows=[]
 for key,base in DEFAULTS.items():
  row={**base,**config.get(key,{}),'id':key}
  from worker import runtime
  row['runtime']=runtime(key)
  rows.append(row)
 return rows
def save_schedule(data):
 if not accounts.admin():raise PermissionError()
 key=data['id']
 if key not in DEFAULTS:raise ValueError()
 base=DEFAULTS[key];item={'enabled':data.get('enabled',True)}
 if type(item['enabled']) is not bool:raise ValueError()
 if base['kind']=='calendar':
  value=data.get('time',base['time'])
  if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',str(value)):raise ValueError('Hora inválida.')
  item['time']=value
 else:
  value=data.get('seconds',base['seconds'])
  if type(value) is not int or not 5<=value<=3600:raise ValueError('Intervalo entre 5 e 3600 segundos.')
  item['seconds']=value
 path=app.ROOT/'schedules.json'
 try:config=json.loads(path.read_text())
 except (OSError,ValueError):config={}
 config[key]=item
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(config));temp.replace(path)
 return {'ok':True,'message':'Guardado. O sistema aplica a alteração em até um minuto.'}
def tasks(data=None):
 with app.db() as c:
  if data:
   action=data.get('action','save')
   if action=='delete':
    c.execute('DELETE FROM tasks WHERE id=? AND owner=?',(int(data['id']),accounts.uid()))
   else:
    title=str(data.get('title','')).strip();notes=str(data.get('notes',''));due=str(data.get('due',''));state=data.get('state','pending')
    if not 1<=len(title)<=200 or len(notes)>4000 or state not in ('pending','doing','done'):raise ValueError('Tarefa inválida.')
    if due:datetime.date.fromisoformat(due)
    if data.get('id'):c.execute('UPDATE tasks SET title=?,notes=?,due=?,state=? WHERE id=? AND owner=?',(title,notes,due,state,int(data['id']),accounts.uid()))
    else:c.execute('INSERT INTO tasks(title,notes,due,state,owner) VALUES(?,?,?,?,?)',(title,notes,due,state,accounts.uid()))
  return [dict(r) for r in c.execute("SELECT * FROM tasks WHERE owner=? ORDER BY state='done',due='',due,id DESC",(accounts.uid(),))]
def health():
 rows=[]
 for name,url in [('Emby',os.getenv('CADENCE_EMBY_URL','http://emby:8096')+'/emby/System/Info/Public'),('Soulseek',os.getenv('CADENCE_SOURCE_URL','http://slskd:5030'))]:
  try:
   with urllib.request.urlopen(url,timeout=3) as r:ok=r.status==200
  except OSError:ok=False
  rows.append({'name':name,'online':ok})
 return rows

def activity(params=None):
 import library
 library.init();params=params or {}
 kind=params.get('kind',['all'])[0];term=params.get('search',[''])[0][:200]
 offset=max(0,min(100000,int(params.get('offset',['0'])[0])))
 if kind not in ('all','search','download','import','library'):raise ValueError()
 with app.db() as c:
  marker=c.execute("SELECT 1 FROM settings WHERE key='activity_migrated'").fetchone()
  if not marker:
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='acquisition_jobs'").fetchone():
    c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) SELECT updated,track_id,CASE WHEN state='completed' THEN 'import' WHEN state='downloading' THEN 'download' ELSE 'search' END,state,'Estado existente ao iniciar o registo: '||detail FROM acquisition_jobs WHERE NOT EXISTS(SELECT 1 FROM activity_log a WHERE a.track_id=acquisition_jobs.track_id)")
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='acquisition_starts'").fetchone():
    c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) SELECT created,track_id,'download','started','Tentativa de transferência (histórico existente)' FROM acquisition_starts")
   c.execute("INSERT INTO settings VALUES('activity_migrated','1')")
  where="WHERE (?='all' OR a.kind=?) AND instr(lower(coalesce(t.artist,'')||' '||coalesce(t.title,'')||' '||a.detail),lower(?))>0"
  values=(kind,kind,term)
  total=c.execute('SELECT count(*) FROM activity_log a LEFT JOIN tracks t ON t.id=a.track_id '+where,values).fetchone()[0]
  rows=[dict(r) for r in c.execute('SELECT a.*,t.artist,t.title FROM activity_log a LEFT JOIN tracks t ON t.id=a.track_id '+where+' ORDER BY a.created DESC,a.id DESC LIMIT 50 OFFSET ?',(*values,offset))]
 return {'entries':rows,'total':total,'offset':offset,'page_size':50}
