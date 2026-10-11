"""Interactive integration setup; secrets are stored only in the state volume."""
import getpass,json,pathlib,urllib.request,os
import app

def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.chmod(0o600);tmp.replace(path)

def main():
 url=input('Emby internal URL [http://emby:8096]: ').strip() or 'http://emby:8096'
 token=getpass.getpass('Emby API key: ').strip()
 req=urllib.request.Request(url.rstrip('/')+'/Users',headers={'X-Emby-Token':token})
 with urllib.request.urlopen(req,timeout=20) as response:users=json.load(response)
 for user in users:print(user['Name']+' → '+user['Id'])
 name=input('Emby username to associate with the Cadence administrator: ').strip()
 user=next((u for u in users if u['Name'].casefold()==name.casefold()),None)
 if not user:raise ValueError('Emby user not found; no changes made.')
 save(app.ROOT/'emby-connection.json',{'url':url.rstrip('/'),'token':token,'user_id':user['Id']})
 with app.db() as c:c.execute('UPDATE users SET emby_id=? WHERE id=1',(user['Id'],))
 import playlists
 playlists.ensure_lanes()
 username=input('Soulseek username (blank to configure later): ').strip()
 if username:
  password=getpass.getpass('Soulseek password: ')
  path=pathlib.Path('/data/appdata/slskd/slskd.yml');cfg=json.loads(path.read_text());cfg['soulseek']={'username':username,'password':password};save(path,cfg)
 print('Saved. Restart slskd if its configuration changed. Downloads remain paused until you resume them in Cadence.')

if __name__=='__main__':main()
