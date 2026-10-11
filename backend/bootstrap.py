"""Initialize empty mounts; never import private deployment data."""
import json,os,pathlib,secrets
import app,accounts,acquisition,playlists,library,remaster,redistribution

def main():
 paths=[app.ROOT,pathlib.Path('/data/media'),pathlib.Path('/data/downloads/slskd'),pathlib.Path('/data/downloads/slskd/incomplete'),app.MEDIA,app.MEDIA/'Singles',pathlib.Path('/data/downloads/slskd/complete'),pathlib.Path('/data/appdata/slskd'),pathlib.Path('/data/appdata/emby'),pathlib.Path('/data/media/redistribution'),pathlib.Path('/data/temporary'),pathlib.Path('/var/backups/media-center')]
 for path in paths:path.mkdir(parents=True,exist_ok=True)
 password=app.ROOT/'admin-password.txt'
 if not password.exists():
  password.write_text(pathlib.Path('/run/secrets/admin_password').read_text().strip());password.chmod(0o600)
 app.init();accounts.init();playlists.init();acquisition.init();library.init();remaster.init();redistribution.init()
 config=pathlib.Path('/data/appdata/slskd/slskd.yml')
 if not config.exists():
  key=secrets.token_hex(32)
  source={'web':{'authentication':{'username':'admin','password':secrets.token_urlsafe(24),'api_keys':{'cadence':{'key':key,'role':'Administrator'}}}},'directories':{'incomplete':'/downloads/incomplete','downloads':'/downloads/complete'},'shares':{'directories':['/redistribution']}}
  config.write_text(json.dumps(source,indent=2));config.chmod(0o600)
  connection=app.ROOT/'source-connection.json';connection.write_text(json.dumps({'url':os.getenv('CADENCE_SOURCE_URL','http://slskd:5030/api/v0'),'api_key':key}));connection.chmod(0o600)
 uid=int(os.getenv('PUID','1000'));gid=int(os.getenv('PGID','1000'))
 for top in paths:
  os.chown(top,uid,gid)
  # Initialization owns application state only; existing music is never recursively changed.
  if top in (app.ROOT,pathlib.Path('/data/appdata/slskd')):
   for child in top.iterdir():os.chown(child,uid,gid)

if __name__=='__main__':main()
