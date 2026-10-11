"""Container scheduler: independent subprocesses, no host/systemd privileges."""
import datetime,json,os,pathlib,subprocess,sys,time
from zoneinfo import ZoneInfo
import app

def runtime(key):
 try:return json.loads((app.ROOT/'worker-runtime.json').read_text()).get(key,{})
 except (OSError,ValueError):return {}

def main():
 from operations import DEFAULTS
 jobs={};last={};calendar={};next_due={}
 extra={'redistribution':{'kind':'interval','seconds':60,'enabled':True}}
 while True:
  now=time.time();today=datetime.datetime.now(ZoneInfo(os.getenv('TZ','UTC')))
  try:settings=json.loads((app.ROOT/'schedules.json').read_text())
  except (OSError,ValueError):settings={}
  state={}
  for key,base in (DEFAULTS|extra).items():
   cfg=base|settings.get(key,{})
   if key in jobs and jobs[key].poll() is not None:
    last[key]=now;jobs.pop(key)
   enabled=cfg.get('enabled',True)
   ready=(app.ROOT/'emby-connection.json').exists() and (app.ROOT/'source-connection.json').exists()
   if key in ('daily','search','acquisition','redistribution') and not ready:enabled=False
   if cfg['kind']=='interval':due=now>=last.get(key,0)+max(5,int(cfg['seconds']))
   else:
    date=today.date().isoformat();due=today.strftime('%H:%M')>=cfg['time'] and calendar.get(key)!=date
   if enabled and due and key not in jobs:
    command=[sys.executable,'-B',('acquisition' if key=='search' else key)+'.py']
    if key=='search':command.append('--search-only')
    jobs[key]=subprocess.Popen(command,cwd=pathlib.Path(__file__).parent)
    if cfg['kind']=='calendar':calendar[key]=today.date().isoformat()
   state[key]={'ActiveState':'active' if enabled else 'inactive','LastTriggerUSec':last.get(key,0),'running':key in jobs}
  target=app.ROOT/'worker-runtime.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(state));temp.replace(target)
  time.sleep(2)

if __name__=='__main__':main()
