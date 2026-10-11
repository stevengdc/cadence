"""Media Center: preference storage, discovery and assisted acquisition staging."""
import argparse, csv, hashlib, hmac, json, os, pathlib, secrets, shutil, sqlite3
import subprocess, time, unicodedata, re, urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs

ROOT = pathlib.Path(os.getenv('MC_STATE', '/var/lib/media-center'))
MEDIA = pathlib.Path(os.getenv('MC_MEDIA', '/data/media/music'))
POLICY = {'mode': 'learning', 'downloads_enabled': False, 'retry_minutes': 60,
          'concurrency': 2, 'reserve_gb': 100, 'exploration_percent': 20, 'min_lossy_kbps':256}

def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text).casefold()
                   if c.isalnum() and not unicodedata.combining(c))

@contextmanager
def db():
    con = sqlite3.connect(ROOT / 'profile.sqlite', timeout=20)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()

def init():
    ROOT.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tracks (
          id INTEGER PRIMARY KEY, artist TEXT NOT NULL, title TEXT NOT NULL,
          track_key TEXT UNIQUE NOT NULL, seed INTEGER NOT NULL DEFAULT 0,
          rating INTEGER NOT NULL DEFAULT 0 CHECK(rating IN (-1,0,1,2)),
          path TEXT, genre TEXT DEFAULT '', duration REAL, updated INTEGER);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, created INTEGER, kind TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS preview_catalog (
          track_id INTEGER PRIMARY KEY REFERENCES tracks(id), deezer_id INTEGER NOT NULL,
          artist TEXT NOT NULL, title TEXT NOT NULL, checked INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS recommendations (
          track_id INTEGER PRIMARY KEY REFERENCES tracks(id), position INTEGER NOT NULL,
          score REAL NOT NULL, reason TEXT NOT NULL, kind TEXT NOT NULL, created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS acquisition_queue (
          track_id INTEGER PRIMARY KEY REFERENCES tracks(id),
          lane TEXT NOT NULL CHECK(lane IN ('style','global','portuguese')),
          state TEXT NOT NULL DEFAULT 'suggested' CHECK(state IN ('suggested','approved','dismissed')),
          created INTEGER NOT NULL, updated INTEGER NOT NULL);
        ''')
        con.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('policy', json.dumps(POLICY)))
        con.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('preferences', ''))
    password = ROOT / 'admin-password.txt'
    if not password.exists():
        password.write_text(secrets.token_urlsafe(18))
        password.chmod(0o600)
    key = ROOT / 'session-key'
    if not key.exists():
        key.write_text(secrets.token_hex(32)); key.chmod(0o600)

def event(con, kind, payload):
    con.execute('INSERT INTO events(created,kind,payload) VALUES (?,?,?)',
                (int(time.time()), kind, json.dumps(payload, ensure_ascii=False)))

def import_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f, db() as con:
        for row in csv.DictReader(f):
            artist, title = row['artist'].strip(), row['title'].strip()
            if not artist or not title: continue
            key = norm(artist) + '|' + norm(title)
            con.execute('''INSERT INTO tracks(artist,title,track_key,seed,updated) VALUES (?,?,?,1,?)
                ON CONFLICT(track_key) DO UPDATE SET seed=1''', (artist,title,key,int(time.time())))
        event(con, 'seed_import', {'source': pathlib.Path(path).name})

def scan():
    errors = 0; scanned = 0
    with db() as con:
        # Clear availability only within this managed collection. Ratings survive re-scans.
        con.execute('UPDATE tracks SET path=NULL WHERE path IS NOT NULL')
        for p in sorted(MEDIA.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in {'.mp3','.flac','.m4a','.ogg','.opus','.wav','.aac'}: continue
            try:
                result = subprocess.run(['ffprobe','-v','error','-show_format','-of','json',str(p)],
                                        capture_output=True, text=True, timeout=20, check=True)
                fmt = json.loads(result.stdout)['format']
                tags = {k.casefold():v for k,v in fmt.get('tags',{}).items()}
                artist = tags.get('artist') or p.parent.name
                title = tags.get('title') or p.stem.removeprefix(artist + ' - ')
                key = norm(artist) + '|' + norm(title)
                con.execute('''INSERT INTO tracks(artist,title,track_key,path,genre,duration,updated)
                    VALUES (?,?,?,?,?,?,?) ON CONFLICT(track_key) DO UPDATE SET
                    path=excluded.path,genre=excluded.genre,duration=excluded.duration,updated=excluded.updated''',
                    (artist,title,key,str(p),tags.get('genre',''),float(fmt.get('duration',0)),int(time.time())))
                scanned += 1
            except (OSError,ValueError,KeyError,subprocess.SubprocessError): errors += 1
        event(con, 'scan', {'scanned': scanned, 'errors': errors})
    print(json.dumps({'scanned':scanned,'errors':errors}))

def status():
    with db() as con:
        count = dict(con.execute('''SELECT count(*) total, sum(seed) seed,
          sum(path IS NOT NULL) available, sum(rating<>0) rated FROM tracks''').fetchone())
        policy = json.loads(con.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0])
        prefs = con.execute("SELECT value FROM settings WHERE key='preferences'").fetchone()[0]
        online_previews = con.execute('SELECT count(*) FROM preview_catalog c JOIN tracks t ON t.id=c.track_id WHERE t.path IS NULL').fetchone()[0]
        recommendation_count = con.execute('SELECT count(*) FROM recommendations').fetchone()[0]
        discovery = con.execute("SELECT value FROM settings WHERE key='discovery_report'").fetchone()
        artists = [dict(r) for r in con.execute('''SELECT artist, sum(CASE rating WHEN 2 THEN 3 WHEN 1 THEN 1
          WHEN -1 THEN -3 ELSE 0 END) weight FROM tracks WHERE rating<>0 GROUP BY artist ORDER BY weight DESC''')]
        events = [dict(r) for r in con.execute('SELECT created,kind,payload FROM events ORDER BY id DESC LIMIT 10')]
    disk = shutil.disk_usage(MEDIA)
    return {'counts':count,'policy':policy,'preferences':prefs,'artists':artists,'events':events,'online_previews':online_previews,
            'free_gb':round(disk.free/1024**3,1),'phase':2 if discovery else 1,
            'discovery_connected':bool(discovery),'openai_connected':False,
            'recommendation_count':recommendation_count,'discovery_report':json.loads(discovery[0]) if discovery else None}

LANES = {'style':'O meu estilo','global':'Tops','portuguese':'Portuguesas'}

def source_status():
    try:
        config=json.loads((ROOT/'source-connection.json').read_text())
        req=urllib.request.Request(config['url']+'/server',headers={'X-API-Key':config['api_key']})
        with urllib.request.urlopen(req,timeout=3) as response: state=json.load(response)
        return {'ready':True,'connected':bool(state.get('isLoggedIn')), 'message':
                'Conta Soulseek ligada.' if state.get('isLoggedIn') else 'Falta ligar a tua conta Soulseek.'}
    except (OSError,ValueError,KeyError):
        return {'ready':False,'connected':False,'message':'Serviço de pesquisa indisponível.'}

def queue_seed():
    with db() as con:
        con.execute("DELETE FROM acquisition_queue WHERE state='suggested' AND track_id IN (SELECT id FROM tracks WHERE rating<=0 OR path IS NOT NULL)")
        con.execute("""INSERT OR IGNORE INTO acquisition_queue(track_id,lane,created,updated)
          SELECT id,'style',?,? FROM tracks WHERE rating>0 AND path IS NULL""",(int(time.time()),int(time.time())))

def queue_status():
    queue_seed()
    with db() as con:
        rows=[dict(r) for r in con.execute("""SELECT t.id,t.artist,t.title,t.rating,q.lane,q.state,c.deezer_id,
          CASE WHEN t.rating<=0 THEN 1 ELSE 0 END blocked FROM acquisition_queue q
          JOIN tracks t ON t.id=q.track_id LEFT JOIN preview_catalog c ON c.track_id=t.id
          WHERE t.path IS NULL ORDER BY t.rating DESC,t.artist,t.title""")]
    return {'source':source_status(),'executor_enabled':status()['policy']['downloads_enabled'],'lanes':LANES,'tracks':rows}

def sample_path(track):
    if not track['path']: return None
    source = pathlib.Path(track['path']).resolve()
    if not source.is_relative_to(MEDIA.resolve()) or not source.is_file(): return None
    key = hashlib.sha256((str(source)+str(source.stat().st_mtime_ns)).encode()).hexdigest()[:20]
    return ROOT / 'samples' / (str(track['id'])+'-'+key+'.mp3')

def samples():
    (ROOT/'samples').mkdir(exist_ok=True)
    with db() as con: rows = con.execute('SELECT id,path,duration FROM tracks WHERE path IS NOT NULL').fetchall()
    made = errors = 0
    for track in rows:
        target = sample_path(track)
        if target is None: errors += 1; continue
        if target.is_file(): continue
        start = max(0,min(45,(track['duration'] or 0)/3))
        temp = target.with_suffix('.tmp.mp3')
        try:
            subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(start),'-i',track['path'],
                            '-t','30','-vn','-map_metadata','-1','-codec:a','libmp3lame','-b:a','128k',
                            '-af','afade=t=in:d=0.3,afade=t=out:st=29:d=1',str(temp)],
                           check=True,capture_output=True,timeout=60)
            temp.replace(target); made += 1
        except (OSError,subprocess.SubprocessError):
            temp.unlink(missing_ok=True); errors += 1
    print(json.dumps({'samples_created':made,'errors':errors}))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass  # Do not record passwords, cookies or listening preferences in access logs.
    def send(self, code, payload, cookie=None, html=False):
        data = payload.encode() if html else json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-src https://widget.deezer.com; frame-ancestors 'none'")
        self.send_header('Content-Length',str(len(data)))
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(data)
    def legacy_authenticated(self):
        try:
            c=SimpleCookie(self.headers.get('Cookie','')); token=c['mc_session'].value
            expiry, sig=token.split('.')
            expected=hmac.new((ROOT/'session-key').read_bytes(),expiry.encode(),hashlib.sha256).hexdigest()
            return int(expiry)>time.time() and hmac.compare_digest(sig,expected)
        except (KeyError,ValueError): return False
    def authenticated(self):
        import accounts
        accounts.init()
        accounts.CURRENT.set(1)
        try:
            cookie=SimpleCookie(self.headers.get('Cookie',''))
            return accounts.authenticate(cookie['mc_session'].value)
        except (KeyError,ValueError): return False
    def audio(self, track_id, head=False, review_file=False):
        if review_file:
            import review,accounts,mimetypes
            if not accounts.admin():return self.send(403,{'error':'Só administradores podem rever ficheiros.'})
            try:_,target,_=review.retained(track_id)
            except (ValueError,OSError):return self.send(404,{'error':'Ficheiro de revisão indisponível.'})
        else:
            with db() as con: track = con.execute('SELECT id,path FROM tracks WHERE id=?',(track_id,)).fetchone()
            target = sample_path(track) if track else None
        if target is None or not target.is_file(): return self.send(404,{'error':'Prévia ainda indisponível.'})
        size = target.stat().st_size; start = 0; end = size-1; code = 200
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not match or not any(match.groups()): return self.send(416,{'error':'Intervalo inválido.'})
            left,right = match.groups()
            if left:
                start=int(left); end=min(int(right),size-1) if right else size-1
            else: start=max(0,size-int(right))
            if start> end or start>=size:
                self.send_response(416); self.send_header('Content-Range',f'bytes */{size}')
                self.send_header('Content-Length','0'); self.end_headers(); return
            code=206
        self.send_response(code); self.send_header('Content-Type', (mimetypes.guess_type(str(target))[0] or 'application/octet-stream') if review_file else 'audio/mpeg')
        self.send_header('Accept-Ranges','bytes'); self.send_header('Cache-Control','private, no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(end-start+1))
        if code==206: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if not head:
            with target.open('rb') as f:
                f.seek(start); self.wfile.write(f.read(end-start+1))
    def do_HEAD(self):
        if not self.authenticated(): return self.send(401,{'error':'Inicia sessão.'})
        match=re.fullmatch(r'/api/sample/(\d+)',urlparse(self.path).path)
        if match: return self.audio(int(match[1]),head=True)
        match=re.fullmatch(r'/api/review-audio/(\d+)',urlparse(self.path).path)
        if match:return self.audio(int(match[1]),head=True,review_file=True)
        self.send(404,{'error':'Não encontrado.'})
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/health': return self.send(200,{'ok':True})
        if p.path=='/':
            target=pathlib.Path(__file__).parent/'web'/'index.html'
            if not target.exists():target=pathlib.Path(__file__).with_name('index.html')
            return self.send(200,target.read_text(),html=True)
        if p.path.startswith('/assets/'):
            root=(pathlib.Path(__file__).parent/'web').resolve();target=(root/p.path.lstrip('/')).resolve()
            if not target.is_relative_to(root/'assets') or not target.is_file():return self.send(404,{'error':'Não encontrado.'})
            import mimetypes
            content=target.read_bytes();self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','public,max-age=31536000,immutable')
            self.end_headers();self.wfile.write(content);return
        if not self.authenticated(): return self.send(401,{'error':'Inicia sessão.'})
        match=re.fullmatch(r'/api/sample/(\d+)',p.path)
        if match: return self.audio(int(match[1]))
        match=re.fullmatch(r'/api/review-audio/(\d+)',p.path)
        if match:return self.audio(int(match[1]),review_file=True)
        if p.path=='/api/review':
            import review,accounts
            if not accounts.admin():return self.send(403,{'error':'Só administradores podem rever ficheiros.'})
            try:return self.send(200,review.details(int(parse_qs(p.query).get('id',['0'])[0])))
            except (ValueError,OSError,subprocess.SubprocessError):return self.send(409,{'error':'Ficheiro ausente ou ambíguo. Podes pesquisar outra fonte.'})

        import accounts,operations
        if p.path=='/api/deployment':return self.send(200,{'emby_url':os.getenv('CADENCE_EMBY_PUBLIC_URL','http://localhost:8096'),'source_url':os.getenv('CADENCE_SOURCE_PUBLIC_URL','http://localhost:5030')})
        if p.path=='/api/me': return self.send(200,accounts.me())
        if p.path=='/api/redistribution':
            import redistribution
            if not accounts.admin():return self.send(403,{'error':'Só administradores.'})
            return self.send(200,redistribution.inventory())
        if p.path=='/api/library':
            import library
            return self.send(200,library.inventory())
        if p.path=='/api/activity':
            try:return self.send(200,operations.activity(parse_qs(p.query)))
            except ValueError:return self.send(400,{'error':'Filtro inválido.'})
        if p.path=='/api/tasks': return self.send(200,operations.tasks())
        if p.path=='/api/automations': return self.send(200,operations.schedules())
        if p.path=='/api/services': return self.send(200,operations.health())
        if p.path=='/api/users':
            if not accounts.admin():return self.send(403,{'error':'Só administradores.'})
            return self.send(200,accounts.users())
        if p.path in ('/api/playlists','/api/playlist','/api/daily'):
            import playlists
            try:
                if p.path=='/api/playlists': return self.send(200,playlists.playlists())
                if p.path=='/api/playlist': return self.send(200,playlists.detail(parse_qs(p.query).get('id',[''])[0]))
                from daily import view
                return self.send(200,accounts.overlay_daily(view(parse_qs(p.query).get('day',[None])[0])))
            except (OSError,ValueError,KeyError): return self.send(503,{'error':'Não foi possível consultar o serviço. Tenta novamente.'})
        if p.path=='/api/acquisition':
            import acquisition
            return self.send(200,acquisition.status())
        if p.path=='/api/queue': return self.send(200,queue_status())
        if p.path=='/api/status':
            result=status()
            if accounts.uid()!=1:
                with db() as c:
                    result['counts']['rated']=c.execute('SELECT count(*) FROM user_ratings WHERE user_id=? AND rating<>0',(accounts.uid(),)).fetchone()[0]
                    pref=c.execute("SELECT value FROM user_settings WHERE user_id=? AND key='preferences'",(accounts.uid(),)).fetchone()
                    result['preferences']=pref[0] if pref else ''
                    result['artists']=[];result['events']=[]
            return self.send(200,result)
        if p.path=='/api/recommendations':
            with db() as con:
                rows=[dict(r) for r in con.execute('''SELECT t.id,t.artist,t.title,t.rating,r.reason,r.kind,r.score,c.deezer_id
                FROM recommendations r JOIN tracks t ON t.id=r.track_id
                JOIN preview_catalog c ON c.track_id=t.id ORDER BY r.position''')]
            return self.send(200,rows)
        if p.path=='/api/tracks':
            q=parse_qs(p.query).get('search',[''])[0][:200]
            with db() as con:
                rows=[dict(r) for r in con.execute('''SELECT t.id,t.artist,t.title,t.seed,t.rating,t.path,t.genre,c.deezer_id
                  FROM tracks t LEFT JOIN preview_catalog c ON c.track_id=t.id
                  WHERE instr(lower(t.artist||' '||t.title),lower(?))>0
                  ORDER BY t.seed DESC,t.artist,t.title LIMIT 1000''',(q,))]
            for row in rows:
                target=sample_path(row); row['local_preview']=bool(target and target.is_file())
                row['preview']=row['local_preview'] or bool(row['deezer_id'])
                row['available']=bool(row.pop('path'))
            return self.send(200,accounts.overlay_tracks(rows))
        self.send(404,{'error':'Não encontrado.'})
    def do_POST(self):
        try:
            if self.headers.get('Origin') != 'http://' + self.headers.get('Host',''):
                return self.send(403,{'error':'Origem inválida.'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.send(415,{'error':'JSON obrigatório.'})
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=20000: return self.send(413,{'error':'Pedido inválido.'})
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValueError()
            import accounts,operations
            accounts.init()
            if self.path=='/api/login':
                token=accounts.login(data)
                if not token:
                    time.sleep(1);return self.send(401,{'error':'Utilizador ou password incorretos.'})
                return self.send(200,{'ok':True},f'mc_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if not self.authenticated(): return self.send(401,{'error':'Inicia sessão.'})
            if self.path=='/api/logout':
                with db() as c:
                    token=SimpleCookie(self.headers.get('Cookie',''))['mc_session'].value
                    c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
                return self.send(200,{'ok':True},'mc_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if self.path=='/api/account':return self.send(200,accounts.update(data))
            if self.path=='/api/user-create':return self.send(200,accounts.create(data))
            if self.path in ('/api/library-remove','/api/library-restore'):
                import library
                try:result=library.remove(int(data['id'])) if self.path=='/api/library-remove' else library.restore(str(data['id']))
                except ValueError as error:return self.send(409,{'error':str(error)})
                return self.send(200,result)
            if self.path=='/api/redistribution':
                import redistribution
                try:return self.send(200,redistribution.control(data))
                except ValueError as error:return self.send(409,{'error':str(error)})
            if self.path=='/api/tasks':return self.send(200,operations.tasks(data))
            if self.path=='/api/automations':return self.send(200,operations.save_schedule(data))
            if self.path=='/api/defer':return self.send(200,accounts.defer(int(data['id'])))
            if self.path in ('/api/policy','/api/acquisition-control','/api/queue') and not accounts.admin():
                return self.send(403,{'error':'Só administradores podem alterar o sistema.'})
            if self.path=='/api/review-control':
                import review
                try:return self.send(200,review.control(data))
                except ValueError as error:return self.send(409,{'error':str(error)})
            if self.path=='/api/acquisition-control':
                import acquisition
                try: return self.send(200,acquisition.control(data))
                except OSError:return self.send(503,{'error':'Serviço de downloads indisponível.'})
            if self.path in ('/api/playlist-create','/api/playlist-add','/api/playlist-remove','/api/daily-decision'):
                import playlists
                try:
                    if self.path=='/api/playlist-create': result={'id':playlists.create(data['name'])}
                    elif self.path=='/api/playlist-add': result=playlists.add(data['playlist_id'],int(data['track_id']))
                    elif self.path=='/api/playlist-remove': result=playlists.remove(data['playlist_id'],data)
                    else: result=playlists.approve(data)
                    return self.send(200,result)
                except OSError: return self.send(503,{'error':'Emby indisponível. A escolha não foi concluída; tenta novamente.'})
            with db() as con:
                if self.path=='/api/rating':
                    if type(data.get('rating')) is not int or data['rating'] not in [-1,0,1,2]: raise ValueError()
                    if accounts.uid()!=1:
                        if not con.execute('SELECT 1 FROM tracks WHERE id=?',(int(data['id']),)).fetchone():raise ValueError()
                        con.execute('INSERT OR REPLACE INTO user_ratings VALUES(?,?,?)',(accounts.uid(),int(data['id']),data['rating']))
                        return self.send(200,{'ok':True})
                    cur=con.execute('UPDATE tracks SET rating=?,updated=? WHERE id=?',
                                    (data['rating'],int(time.time()),int(data['id'])))
                    if cur.rowcount!=1: return self.send(404,{'error':'Música inexistente.'})
                    event(con,'rating',{'id':data['id'],'rating':data['rating']})
                elif self.path=='/api/queue':
                    track_id=int(data['id']); action=data['action']
                    if action not in ('approve','dismiss','reset','lane'): raise ValueError()
                    row=con.execute('SELECT t.rating,t.path FROM acquisition_queue q JOIN tracks t ON t.id=q.track_id WHERE q.track_id=?',(track_id,)).fetchone()
                    if row is None: return self.send(404,{'error':'Música inexistente na fila.'})
                    if action=='approve' and (row['rating']<=0 or row['path']):
                        return self.send(409,{'error':'Só podes aprovar músicas de que gostas e que ainda não tens.'})
                    if action=='lane':
                        lane=data['lane']
                        if lane not in LANES: raise ValueError()
                        con.execute('UPDATE acquisition_queue SET lane=?,updated=? WHERE track_id=?',(lane,int(time.time()),track_id))
                    else:
                        state={'approve':'approved','dismiss':'dismissed','reset':'suggested'}[action]
                        con.execute('UPDATE acquisition_queue SET state=?,updated=? WHERE track_id=?',(state,int(time.time()),track_id))
                    event(con,'queue_changed',{'id':track_id,'action':action})
                elif self.path=='/api/preferences':
                    text=data.get('text','')
                    if not isinstance(text,str) or len(text)>5000: raise ValueError()
                    if accounts.uid()!=1:
                        con.execute('INSERT OR REPLACE INTO user_settings VALUES(?,?,?)',(accounts.uid(),'preferences',text))
                    else:con.execute("UPDATE settings SET value=? WHERE key='preferences'",(text,))
                    event(con,'preferences_changed',{})
                elif self.path=='/api/policy':
                    policy=json.loads(con.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0])
                    for k,low,high in [('retry_minutes',15,1440),('concurrency',1,5),('reserve_gb',20,400),('exploration_percent',0,50)]:
                        v=data.get(k,policy[k])
                        if type(v) is not int or not low<=v<=high: raise ValueError()
                        policy[k]=v
                    # A client cannot enable acquisitions in phase 1.
                    if any(k in data for k in ('downloads_enabled','mode','daily_limit','max_transfer_attempts')): raise ValueError()
                    con.execute("UPDATE settings SET value=? WHERE key='policy'",(json.dumps(policy),))
                    event(con,'policy_changed',policy)
                else: return self.send(404,{'error':'Não encontrado.'})
            return self.send(200,{'ok':True})
        except PermissionError:self.send(403,{'error':'Sem permissão para esta ação.'})
        except OSError:self.send(503,{'error':'Serviço indisponível. Tenta novamente.'})
        except (ValueError,KeyError,TypeError,json.JSONDecodeError): self.send(400,{'error':'Valores inválidos.'})

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--import-csv'); parser.add_argument('--scan',action='store_true')
    parser.add_argument('--samples',action='store_true')
    parser.add_argument('--serve',action='store_true'); args=parser.parse_args(); init()
    if args.import_csv: import_csv(args.import_csv)
    if args.scan: scan()
    if args.samples: samples()
    if args.serve:
        import accounts
        accounts.init()
    if args.serve: ThreadingHTTPServer(('0.0.0.0',8787),Handler).serve_forever()
