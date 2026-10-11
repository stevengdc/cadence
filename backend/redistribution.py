"""Explicit administrator authorization; no implicit sharing."""
import time,json,os,pathlib,shutil,fcntl
import acquisition
import app,accounts,library

EXPORT=pathlib.Path('/data/media/redistribution')
def signature(row):return json.dumps([row['filename'],row['size'],row.get('file_signature',row['modified'])])
def init():
 library.init()
 with app.db() as c:
  c.executescript("CREATE TABLE IF NOT EXISTS redistribution(track_id INTEGER PRIMARY KEY,authorized INTEGER NOT NULL DEFAULT 0,user_id INTEGER,updated INTEGER,signature TEXT);")

def inventory():
 if not accounts.admin():raise PermissionError()
 init()
 data=library.inventory()
 with app.db() as c: grants={r['track_id']:dict(r) for r in c.execute('SELECT * FROM redistribution')}
 for row in data['files']:
  grant=grants.get(row['id'],{})
  row.update(authorized=bool(grant.get('authorized')) and grant.get('signature')==signature(row),authorized_at=grant.get('updated'),eligible=row['codec']=='mp3' and row['bitrate']==320 and row.get('rating',0)>0)
 return data

def control(data):
 if not accounts.admin():raise PermissionError()
 ids=data.get('ids');allowed=data.get('authorized')
 if not isinstance(ids,list) or not ids or len(ids)>500 or any(type(i) is not int for i in ids) or type(allowed) is not bool:raise ValueError('Seleção inválida.')
 ids=list(dict.fromkeys(ids));rows={r['id']:r for r in inventory()['files']}
 if any(i not in rows or (allowed and not rows[i]['eligible']) for i in ids):raise ValueError('Só podes autorizar músicas aprovadas, descarregadas e em MP3 a 320 kbps.')
 now=int(time.time())
 with app.db() as c:
  for tid in ids:
   c.execute('INSERT OR REPLACE INTO redistribution VALUES(?,?,?,?,?)',(tid,int(allowed),accounts.uid(),now,signature(rows[tid])))
   c.execute("INSERT INTO activity_log(created,track_id,kind,state,detail) VALUES(?,?,'library',?,?)",(now,tid,'authorized' if allowed else 'revoked','Redistribuição autorizada pelo administrador' if allowed else 'Autorização de redistribuição revogada'))
 return {'ok':True,'count':len(ids)}


def sync():
 # Same lock as imports/removals; authorization changes are serialized by SQLite.
 with library.exclusive():
  data=inventory();EXPORT.mkdir(parents=True,exist_ok=True);staging=EXPORT.parent/'redistribution-staging';staging.mkdir(exist_ok=True);desired={}
  for row in data['files']:
   if row['authorized'] and row['eligible']:
    with app.db() as c:path=c.execute('SELECT path FROM tracks WHERE id=?',(row['id'],)).fetchone()[0]
    source=library.file_path(path)
    clean=lambda x: ''.join(ch if ch.isalnum() or ch in ' ._-' else '_' for ch in x)[:100]
    target=EXPORT/(str(row['id'])+' - '+clean(row['artist'])+' - '+clean(row['title'])+'.mp3')
    desired[target.name]=(source,row)
  changed=False
  for target in EXPORT.iterdir():
   if target.is_file() and target.name not in desired:target.unlink();changed=True
  for name,(source,row) in desired.items():
   target=EXPORT/name
   if not target.exists() or target.stat().st_size!=source.stat().st_size or target.stat().st_mtime_ns!=source.stat().st_mtime_ns:
    temp=staging/(name+'.tmp');shutil.copy2(source,temp);os.chmod(temp,0o644);os.replace(temp,target);changed=True
  # Retry a failed rescan even if the filesystem has already converged.
  marker=app.ROOT/'redistribution-rescan-pending'
  if changed:marker.touch()
  if marker.exists():
   acquisition.api('shares',method='PUT');marker.unlink()
  return {'exported':len(desired)}

if __name__=='__main__':print(json.dumps(sync()))
