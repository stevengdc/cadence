"""Personal accounts, durable sessions and isolated preference overlays."""
import os,contextvars,hashlib,hmac,json,re,secrets,time
import app
CURRENT=contextvars.ContextVar('account',default=1)
def uid():return CURRENT.get()
def hash_password(password,salt=None):
 if not isinstance(password,str) or not 8<=len(password)<=200:raise ValueError('A password precisa de 8 a 200 caracteres.')
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def verify(password,stored):
 try:return hmac.compare_digest(hash_password(password,stored.split(':')[0]),stored)
 except (ValueError,TypeError):return False
def init():
 with app.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE,name TEXT,password TEXT,role TEXT DEFAULT 'member',active INTEGER DEFAULT 1,theme TEXT DEFAULT 'dark',accent TEXT DEFAULT 'teal',emby_id TEXT,created INTEGER DEFAULT(unixepoch()));
  CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires INTEGER);
  CREATE TABLE IF NOT EXISTS user_ratings(user_id INTEGER,track_id INTEGER,rating INTEGER,PRIMARY KEY(user_id,track_id));
  CREATE TABLE IF NOT EXISTS user_decisions(user_id INTEGER,day TEXT,lane TEXT,track_id INTEGER,decision INTEGER,PRIMARY KEY(user_id,day,lane,track_id));
  CREATE TABLE IF NOT EXISTS deferred(user_id INTEGER,track_id INTEGER,until_day TEXT,PRIMARY KEY(user_id,track_id));
  CREATE TABLE IF NOT EXISTS user_lanes(user_id INTEGER,lane TEXT,emby_id TEXT,PRIMARY KEY(user_id,lane));
  CREATE TABLE IF NOT EXISTS owned_playlists(playlist_id TEXT PRIMARY KEY,user_id INTEGER);
  CREATE TABLE IF NOT EXISTS user_settings(user_id INTEGER,key TEXT,value TEXT,PRIMARY KEY(user_id,key));
  CREATE TABLE IF NOT EXISTS user_candidates(user_id INTEGER,day TEXT,lane TEXT,track_id INTEGER,position INTEGER,reason TEXT,PRIMARY KEY(user_id,day,lane,track_id));
  CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT,notes TEXT DEFAULT '',due TEXT DEFAULT '',state TEXT DEFAULT 'pending',owner INTEGER DEFAULT 1,created INTEGER DEFAULT(unixepoch()));''')
  if not c.execute('SELECT 1 FROM users').fetchone():
   try:emby=json.loads((app.ROOT/'emby-connection.json').read_text())['user_id']
   except (OSError,ValueError,KeyError):emby=None
   c.execute('INSERT INTO users(id,username,name,password,role,emby_id) VALUES(1,?,?,?,?,?)',(os.getenv('CADENCE_ADMIN_USER','admin'),os.getenv('CADENCE_ADMIN_NAME','Administrator'),hash_password((app.ROOT/'admin-password.txt').read_text().strip()),'admin',emby))
  if not c.execute('SELECT 1 FROM tasks').fetchone():
   c.execute("INSERT INTO tasks(title,notes) VALUES('Configurar backup externo','Configure a separate backup destination for your library and application state.')")
def public(row):return {k:row[k] for k in ('id','username','name','role','active','theme','accent','emby_id')}
def me():
 with app.db() as c:r=c.execute('SELECT * FROM users WHERE id=?',(uid(),)).fetchone()
 return public(r)
def admin():return me()['role']=='admin'
def login(data):
 username=str(data.get('username','admin')).strip() or 'admin'
 with app.db() as c:
  r=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
  if not r or not verify(data.get('password',''),r['password']):return None
  token=secrets.token_urlsafe(32)
  c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
  c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),r['id'],int(time.time())+28800))
 return token
def authenticate(token):
 with app.db() as c:r=c.execute('SELECT u.id FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=? AND expires>? AND active=1',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
 if not r:return False
 CURRENT.set(r[0]);return True
def update(data):
 target=int(data.get('id',uid()))
 if target!=uid() and not admin():raise PermissionError()
 with app.db() as c:
  r=c.execute('SELECT * FROM users WHERE id=?',(target,)).fetchone()
  if not r:raise ValueError('Conta inexistente.')
  name=str(data.get('name',r['name'])).strip()
  theme=data.get('theme',r['theme']);accent=data.get('accent',r['accent'])
  if not 1<=len(name)<=80 or theme not in ('light','dark','system') or accent not in ('teal','blue','purple','orange'):raise ValueError('Definições inválidas.')
  if data.get('password'):
   if target==uid() and not verify(data.get('current_password',''),r['password']):raise ValueError('Password atual incorreta.')
   password=hash_password(data['password'])
   c.execute('UPDATE users SET password=? WHERE id=?',(password,target));c.execute('DELETE FROM sessions WHERE user_id=?',(target,))
  c.execute('UPDATE users SET name=?,theme=?,accent=? WHERE id=?',(name,theme,accent,target))
  if admin() and target!=1:
   role=data.get('role',r['role']);active=int(data.get('active',r['active']))
   if role not in ('admin','member') or active not in (0,1):raise ValueError()
   if r['emby_id'] and active!=r['active']:
    import operations
    emby_user=operations.emby('Users/'+r['emby_id'])
    emby_policy=emby_user['Policy'];emby_policy['IsDisabled']=not bool(active)
    operations.emby('Users/'+r['emby_id']+'/Policy','POST',emby_policy)
   c.execute('UPDATE users SET role=?,active=? WHERE id=?',(role,active,target))
 return {'ok':True}
def users():
 if not admin():raise PermissionError()
 with app.db() as c:return [public(r) for r in c.execute('SELECT * FROM users ORDER BY id')]
def create(data):
 if not admin():raise PermissionError()
 username=str(data['username']).strip();name=str(data.get('name',username)).strip();password=hash_password(data['password'])
 if not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}',username) or not 1<=len(name)<=80:raise ValueError('Nome de utilizador inválido.')
 with app.db() as c:
  if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():raise ValueError('Utilizador já existe.')
 # Create a separate Emby identity for access through Emby / Symfonium.
 import operations
 result=operations.emby('Users/New','POST',{'Name':username})
 eid=result['Id']
 try:operations.emby('Users/'+eid+'/Password','POST',{'NewPw':data['password'],'ResetPassword':False})
 except OSError:
  try:operations.emby('Users/'+eid,'DELETE')
  except OSError:pass
  raise
 with app.db() as c:
  c.execute('INSERT INTO users(username,name,password,emby_id) VALUES(?,?,?,?)',(username,name,password,eid))
 return {'ok':True}
def defer(tid):
 import datetime
 from zoneinfo import ZoneInfo
 tomorrow=(datetime.datetime.now(ZoneInfo('Europe/Lisbon')).date()+datetime.timedelta(days=1)).isoformat()
 with app.db() as c:
  if not c.execute('SELECT 1 FROM tracks WHERE id=?',(tid,)).fetchone():raise ValueError('Música inexistente.')
  c.execute('INSERT OR REPLACE INTO deferred VALUES(?,?,?)',(uid(),tid,tomorrow))
 return {'ok':True,'until':tomorrow}
def overlay_tracks(rows):
 with app.db() as c:
  ratings={r[0]:r[1] for r in c.execute('SELECT track_id,rating FROM user_ratings WHERE user_id=?',(uid(),))}
  deferred={r[0]:r[1] for r in c.execute('SELECT track_id,until_day FROM deferred WHERE user_id=?',(uid(),))}
  ratings={r[0]:r[1] for r in c.execute('SELECT id,rating FROM tracks')} if uid()==1 else {r[0]:r[1] for r in c.execute('SELECT track_id,rating FROM user_ratings WHERE user_id=?',(uid(),))}
 for r in rows:
  if uid()!=1:r['rating']=ratings.get(r['id'],0)
  r['deferred_until']=deferred.get(r['id'])
 return rows
def overlay_daily(data):
 with app.db() as c:
  if uid()!=1:
   query='SELECT d.day,d.lane,d.track_id,d.position,d.reason,t.artist,t.title,t.path,p.deezer_id FROM user_candidates d JOIN tracks t ON t.id=d.track_id LEFT JOIN preview_catalog p ON p.track_id=t.id WHERE d.user_id=?'
   personal=[dict(r) for r in c.execute(query,(uid(),))]
   if personal:
    data['tracks']=[r for r in data['tracks'] if r['lane']!='style']
    for r in personal:
     r['available']=bool(r.pop('path'));r['decision']=0
    data['tracks']+=personal
    data['days']=sorted(set(data['days'])|{r['day'] for r in personal},reverse=True)
    if data['day']!='all':data['tracks']=[r for r in data['tracks'] if r['day']==data['day']]

  decisions={(r['day'],r['lane'],r['track_id']):r['decision'] for r in c.execute('SELECT * FROM user_decisions WHERE user_id=?',(uid(),))}
  deferred={r[0]:r[1] for r in c.execute('SELECT track_id,until_day FROM deferred WHERE user_id=?',(uid(),))}
  ratings={r[0]:r[1] for r in c.execute('SELECT id,rating FROM tracks')} if uid()==1 else {r[0]:r[1] for r in c.execute('SELECT track_id,rating FROM user_ratings WHERE user_id=?',(uid(),))}
 for r in data['tracks']:
  if uid()!=1:r['decision']=decisions.get((r['day'],r['lane'],r['track_id']),0)
  if uid()!=1 and r['lane']=='style' and not personal:r['reason']='Seleção inicial para conhecer o teu gosto. As tuas avaliações vão orientar as próximas propostas.'
  r['rating']=ratings.get(r['track_id'],0)
  r['deferred_until']=deferred.get(r['track_id'])
 return data
