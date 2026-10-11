"""Server playlists remain authoritative; only explicitly pending additions are reconciled."""
import json,re,urllib.request,urllib.parse,pathlib
import app,accounts

def init():
 accounts.init()
 with app.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS playlist_lanes(lane TEXT PRIMARY KEY,emby_id TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS playlist_pending(playlist_id TEXT NOT NULL,track_id INTEGER NOT NULL,created INTEGER DEFAULT(unixepoch()),PRIMARY KEY(playlist_id,track_id));
   CREATE TABLE IF NOT EXISTS daily_candidates(day TEXT NOT NULL,lane TEXT NOT NULL,track_id INTEGER NOT NULL,position INTEGER,reason TEXT,decision INTEGER DEFAULT 0 CHECK(decision IN (-1,0,1,2)),PRIMARY KEY(day,lane,track_id));
   CREATE TABLE IF NOT EXISTS chart_snapshots(region TEXT PRIMARY KEY,edition TEXT,url TEXT,fetched INTEGER,tracks TEXT,error TEXT);
  ''')
  c.execute("INSERT OR REPLACE INTO settings VALUES ('external_backup',?)",(json.dumps({'state':'pending','reason':'Aguarda formataÃ§Ã£o e partilha do disco de rede; mÃºsica e Immich.'}),))

def config():
 cfg=json.loads((app.ROOT/'emby-connection.json').read_text())
 if accounts.uid()!=1:
  with app.db() as c:row=c.execute('SELECT emby_id FROM users WHERE id=?',(accounts.uid(),)).fetchone()
  if not row or not row[0]:raise ValueError('Conta Emby ainda nÃ£o associada.')
  cfg['user_id']=row[0]
 return cfg
def call(path,method='GET',query=None):
 cfg=config();query={**(query or {}),'UserId':cfg['user_id']}
 url=cfg['url']+'/'+path+'?'+urllib.parse.urlencode(query)
 req=urllib.request.Request(url,data=b'' if method=='POST' else None,method=method,headers={'X-Emby-Token':cfg['token']})
 with urllib.request.urlopen(req,timeout=20) as r:
  data=r.read();return json.loads(data) if data else {}
def safe_id(value):
 if not re.fullmatch(r'[A-Za-z0-9-]{1,80}',str(value)):raise ValueError('ID invÃ¡lido.')
 return str(value)
def playlists():
 rows=call('Items',query={'Recursive':'true','IncludeItemTypes':'Playlist','Fields':'MediaType'})['Items']
 with app.db() as c:owners={r[0]:r[1] for r in c.execute('SELECT playlist_id,user_id FROM owned_playlists')}
 return [{'id':r['Id'],'name':r['Name']} for r in rows if owners.get(r['Id'],1)==accounts.uid()]
def check_playlist(pid):
 pid=safe_id(pid)
 if pid not in {p['id'] for p in playlists()}:raise ValueError('Playlist indisponÃ­vel.')
 return pid
def create(name):
 name=str(name).strip()
 if not 1<=len(name)<=100:raise ValueError('Nome entre 1 e 100 caracteres.')
 if any(p['name'].casefold()==name.casefold() for p in playlists()):raise ValueError('JÃ¡ existe uma playlist com esse nome.')
 pid=call('Playlists','POST',{'Name':name,'MediaType':'Audio'})['Id']
 with app.db() as c:c.execute('INSERT OR REPLACE INTO owned_playlists VALUES(?,?)',(pid,accounts.uid()))
 return pid
def library_map():
 cfg=config();items=call('Items',query={'Recursive':'true','IncludeItemTypes':'Audio','Fields':'Path','Limit':10000})['Items']
 return {i.get('Path'):i['Id'] for i in items}
def audio_id(track):
 if not track['path']:return None
 path=pathlib.Path(track['path']).resolve()
 if not path.is_relative_to(app.MEDIA.resolve()) or not path.is_file():return None
 emby_path='/media/music/'+str(path.relative_to(app.MEDIA.resolve()))
 return library_map().get(emby_path)
def entries(pid):return call('Playlists/'+safe_id(pid)+'/Items',query={'Fields':'Path','Limit':10000})['Items']
def detail(pid):
 pid=check_playlist(pid);items=entries(pid)
 ready=[{'entry_id':r['PlaylistItemId'],'title':r['Name'],'artist':', '.join(r.get('Artists',[])),'ready':True} for r in items]
 with app.db() as c:
  pending=[dict(r) for r in c.execute('SELECT t.id,t.artist,t.title FROM playlist_pending p JOIN tracks t ON t.id=p.track_id WHERE p.playlist_id=?',(pid,))]
 return {'ready':ready,'pending':pending}
def add(pid,tid):
 pid=check_playlist(pid)
 with app.db() as c:track=c.execute('SELECT * FROM tracks WHERE id=?',(int(tid),)).fetchone()
 if track is None:raise ValueError('MÃºsica inexistente.')
 iid=audio_id(track)
 if iid:
  if iid not in {r['Id'] for r in entries(pid)}:call('Playlists/'+pid+'/Items','POST',{'Ids':iid})
  with app.db() as c:c.execute('DELETE FROM playlist_pending WHERE playlist_id=? AND track_id=?',(pid,tid))
  return {'ready':True}
 with app.db() as c:c.execute('INSERT OR IGNORE INTO playlist_pending(playlist_id,track_id) VALUES (?,?)',(pid,tid))
 return {'ready':False}
def remove(pid,data):
 pid=check_playlist(pid)
 if data.get('entry_id'):
  eid=safe_id(data['entry_id'])
  if eid not in {r['PlaylistItemId'] for r in entries(pid)}:raise ValueError('Entrada inexistente.')
  call('Playlists/'+pid+'/Items','DELETE',{'EntryIds':eid})
 else:
  with app.db() as c:c.execute('DELETE FROM playlist_pending WHERE playlist_id=? AND track_id=?',(pid,int(data['track_id'])))
 return {'ok':True}
def ensure_lanes():
 names={'style':'O meu estilo','global':'Tops','portuguese':'Portuguesas'}
 current=playlists()
 for lane,name in names.items():
  with app.db() as c:row=c.execute('SELECT emby_id FROM playlist_lanes WHERE lane=?',(lane,)).fetchone() if accounts.uid()==1 else c.execute('SELECT emby_id FROM user_lanes WHERE user_id=? AND lane=?',(accounts.uid(),lane)).fetchone()
  if row and row[0] in {p['id'] for p in current}:continue
  existing=next((p['id'] for p in current if p['name']==name),None)
  pid=existing or create(name)
  with app.db() as c:
   if accounts.uid()==1:c.execute('INSERT OR REPLACE INTO playlist_lanes VALUES (?,?)',(lane,pid))
   else:c.execute('INSERT OR REPLACE INTO user_lanes VALUES (?,?,?)',(accounts.uid(),lane,pid))
def approve(data):
 if accounts.uid()!=1:ensure_lanes()
 day=data['day'];lane=data['lane'];tid=int(data['id']);decision=data['decision']
 if type(decision) is not int or decision not in (-1,1,2):raise ValueError('Escolhe Adoro, Gosto ou NÃ£o gosto.')
 with app.db() as c:
  row=c.execute('SELECT * FROM daily_candidates WHERE day=? AND lane=? AND track_id=?',(day,lane,tid)).fetchone()
  if accounts.uid()!=1 and lane=='style':
   personal=c.execute('SELECT * FROM user_candidates WHERE user_id=? AND day=? AND lane=? AND track_id=?',(accounts.uid(),day,lane,tid)).fetchone()
   if personal:row={**dict(personal),'decision':0}
  if row is None:raise ValueError('Proposta inexistente.')
  lane_row=c.execute('SELECT emby_id FROM playlist_lanes WHERE lane=?',(lane,)).fetchone() if accounts.uid()==1 else c.execute('SELECT emby_id FROM user_lanes WHERE user_id=? AND lane=?',(accounts.uid(),lane)).fetchone()
  if not lane_row:raise ValueError('Playlist da lista indisponível.')
  pid=lane_row[0]
  if accounts.uid()!=1:
   personal=c.execute('SELECT decision FROM user_decisions WHERE user_id=? AND day=? AND lane=? AND track_id=?',(accounts.uid(),day,lane,tid)).fetchone()
   row={**dict(row),'decision':personal[0] if personal else 0}
 if decision<0 and row['decision']>0:
  with app.db() as c:track=c.execute('SELECT * FROM tracks WHERE id=?',(tid,)).fetchone()
  iid=audio_id(track)
  if iid:
   for entry in entries(pid):
    if entry['Id']==iid:remove(pid,{'entry_id':entry['PlaylistItemId']})
 with app.db() as c:
  if accounts.uid()==1:
   c.execute('UPDATE daily_candidates SET decision=? WHERE day=? AND lane=? AND track_id=?',(decision,day,lane,tid))
   if lane=='style':c.execute('UPDATE tracks SET rating=? WHERE id=?',(decision,tid))
  else:
   c.execute('INSERT OR REPLACE INTO user_decisions VALUES(?,?,?,?,?)',(accounts.uid(),day,lane,tid,decision))
   if lane=='style':c.execute('INSERT OR REPLACE INTO user_ratings VALUES(?,?,?)',(accounts.uid(),tid,decision))
  c.execute('DELETE FROM deferred WHERE user_id=? AND track_id=?',(accounts.uid(),tid))
  if decision<0:c.execute('DELETE FROM playlist_pending WHERE playlist_id=? AND track_id=?',(pid,tid))
  else:c.execute('INSERT OR IGNORE INTO playlist_pending(playlist_id,track_id) VALUES (?,?)',(pid,tid))
  app.event(c,'daily_decision',{'id':tid,'lane':lane,'decision':decision})
 # Persist positive decisions before contacting Emby; reconciliation retries the queue.
 result={'ready':False}
 if decision>0:
  try:result=add(pid,tid)
  except (OSError,ValueError):result={'ready':False,'sync_pending':True}
 return {'ok':True,**result}
def reconcile():
 with app.db() as c:rows=c.execute('SELECT playlist_id,track_id FROM playlist_pending').fetchall()
 for r in rows:
  with app.db() as c:owner=c.execute('SELECT user_id FROM owned_playlists WHERE playlist_id=?',(r[0],)).fetchone()
  token=accounts.CURRENT.set(owner[0] if owner else 1)
  try:add(r[0],r[1])
  except (OSError,ValueError):pass
  finally:accounts.CURRENT.reset(token)
if __name__=='__main__':init();ensure_lanes();reconcile()
