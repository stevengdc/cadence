"""Ten daily proposals per lane, no padded duplicates; weekly charts retain their edition."""
import os,json,re,time,datetime,urllib.request,urllib.parse,tempfile,subprocess,pathlib,collections,hashlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import app,discovery,playlists,accounts
SOURCES={'global':'https://www.billboard.com/charts/billboard-global-200/','uk':'https://www.officialcharts.com/charts/singles-chart/','pt':'https://www.audiogest.pt/tops-semanais-2026?lang=pt'}
PT_ARTISTS=['Jorge Palma','Carolina Deslandes','Bárbara Tinoco','Diogo Piçarra','Mariza','Dillaz','Plutonio','Richie Campbell','Chico da Tina','Vizinhos','Ana Moura','Miguel Araújo','Os Quatro e Meia','Capitão Fausto','Tiago Bettencourt','D.A.M.A']
def today():return datetime.datetime.now(ZoneInfo(os.getenv('TZ','UTC'))).date().isoformat()
def read(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (PersonalMediaCenter)'})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def chart_html(region,html):
 s=BeautifulSoup(html,'html.parser');out=[]
 if region=='uk':
  for row in s.select('.chart-item'):
   rank=row.select_one('.chart-key strong');title=row.select_one('.chart-name');artist=row.select_one('.chart-artist')
   if not all([rank,title,artist]):continue
   rank=int(rank.get_text(strip=True))
   if rank>20:continue
   spans=title.find_all('span',recursive=False);name=spans[-1].get_text(' ',strip=True) if spans else title.get_text(' ',strip=True)
   out.append({'rank':rank,'title':name,'artist':artist.get_text(' ',strip=True)})
  edition=next((p.get_text(' ',strip=True) for p in s.select('p') if re.search(r'\d+ \w+ 202\d - \d+ \w+ 202\d',p.get_text())), '')
 else:
  for row in s.select('.o-chart-results-list-row-container')[:20]:
   title=row.select_one('h3');artist=title.find_next_sibling('span') if title else None
   if title and artist:out.append({'rank':len(out)+1,'title':title.get_text(' ',strip=True),'artist':artist.get_text(' ',strip=True)})
  el=s.select_one('.a-chart-datepicker-opener');edition=el.get_text(' ',strip=True).replace('Datepicker Plus Icon ','') if el else ''
 unique={x['rank']:x for x in out};out=[unique[r] for r in sorted(unique)]
 if [x['rank'] for x in out]!=list(range(1,21)) or not edition:raise ValueError('Chart structure changed')
 return edition,out
def chart_pt():
 url=SOURCES['pt'];html=BeautifulSoup(read(url),'html.parser')
 links=[urllib.parse.urljoin(url,a['href']) for a in html.select('a[href]') if re.search(r'/uploads/files/file_2026-\d\d-\d\d[^/]*\.pdf$',a['href'])]
 if not links:raise ValueError('No weekly chart')
 pdf=max(links);assert urllib.parse.urlparse(pdf).hostname in ('www.audiogest.pt','audiogest.pt')
 with tempfile.TemporaryDirectory() as tmp:
  source=pathlib.Path(tmp)/'chart.pdf';source.write_bytes(read(pdf))
  result=subprocess.run(['pdftotext','-layout',str(source),'-'],capture_output=True,text=True,check=True,timeout=25).stdout
 edition=re.search(r'Semana \d+ de \d{4}',result).group(0)
 section=result.split('\fTOP 200 SINGLES',1)[1];out=[]
 for line in section.splitlines():
  if not re.match(r'^\s*\d+\s',line):continue
  parts=re.split(r'\s{2,}',line.strip())
  if len(parts)<7:continue
  rank=int(parts[0])
  if rank>20:break
  # fixed layout separates rank/statistics/certification from title, artist and distributor
  out.append({'rank':rank,'title':parts[-3],'artist':parts[-2]})
 if [x['rank'] for x in out]!=list(range(1,21)):raise ValueError('Portuguese chart structure changed')
 return edition,out,pdf
def refresh_charts():
 for region,url in SOURCES.items():
  try:
   if region=='pt':edition,rows,url=chart_pt()
   else:edition,rows=chart_html(region,read(url))
   with app.db() as c:c.execute('INSERT OR REPLACE INTO chart_snapshots VALUES (?,?,?,?,?,NULL)',(region,edition,url,int(time.time()),json.dumps(rows,ensure_ascii=False)))
  except (OSError,ValueError,IndexError,AttributeError,subprocess.SubprocessError):
   with app.db() as c:
    c.execute('INSERT OR IGNORE INTO chart_snapshots(region,url,tracks) VALUES (?,?,?)',(region,url,'[]'))
    c.execute('UPDATE chart_snapshots SET error=? WHERE region=?',('Não foi possível atualizar esta fonte; seleção desta fonte suspensa.',region))
def register(candidate):
 with app.db() as c:
  existing=next((r for r in c.execute('SELECT id,artist,title FROM tracks') if discovery.key(r['artist'],r['title'])==discovery.key(candidate['artist'],candidate['title'])),None)
  if existing:tid=existing['id']
  else:
   k=app.norm(candidate['artist'])+'|'+app.norm(candidate['title'])
   c.execute('INSERT OR IGNORE INTO tracks(artist,title,track_key,updated) VALUES (?,?,?,?)',(candidate['artist'],candidate['title'],k,int(time.time())))
   tid=c.execute('SELECT id FROM tracks WHERE track_key=?',(k,)).fetchone()[0]
  if candidate.get('deezer_id'):c.execute('INSERT OR REPLACE INTO preview_catalog VALUES (?,?,?,?,?)',(tid,candidate['deezer_id'],candidate['artist'],candidate['title'],int(time.time())))
 return tid
def match_preview(candidate):
 try:
  q=urllib.parse.urlencode({'q':candidate['artist']+' '+candidate['title'],'limit':15})
  for t in discovery.fetch('search?'+q).get('data',[]):
   a=discovery.artist_key(t['artist']['name']);expected=discovery.artist_key(candidate['artist'])
   if discovery.title_key(t['title'])==discovery.title_key(candidate['title']) and (a==expected or expected.startswith(a)) and discovery.valid(t):
    return {**candidate,'deezer_id':int(t['id'])}
 except (OSError,ValueError,KeyError):pass
 return candidate
def choose(pool,seen,limit=10):
 result=[];artists=collections.Counter();keys=set(seen)
 for t in pool:
  k=discovery.key(t['artist'],t['title']);a=discovery.artist_key(t['artist'])
  if k in keys or artists[a]>=2:continue
  result.append(t);keys.add(k);artists[a]+=1
  if len(result)==limit:break
 return result
def store(day,lane,pool):
 if accounts.uid()!=1:
  with app.db() as c:
   if c.execute('SELECT 1 FROM user_candidates WHERE user_id=? AND day=? AND lane=?',(accounts.uid(),day,lane)).fetchone():return
   seen={discovery.key(r['artist'],r['title']) for r in c.execute('SELECT t.artist,t.title FROM user_candidates d JOIN tracks t ON t.id=d.track_id WHERE d.user_id=? AND d.lane=?',(accounts.uid(),lane))}
   seen|={discovery.key(r['artist'],r['title']) for r in c.execute('SELECT t.artist,t.title FROM user_ratings r JOIN tracks t ON t.id=r.track_id WHERE r.user_id=? AND r.rating<>0',(accounts.uid(),))}
  for pos,t in enumerate(choose(pool,seen)):
   tid=register(t)
   with app.db() as c:c.execute('INSERT OR IGNORE INTO user_candidates VALUES(?,?,?,?,?,?)',(accounts.uid(),day,lane,tid,pos,t['reason']))
  return
 with app.db() as c:
  if c.execute('SELECT 1 FROM daily_candidates WHERE day=? AND lane=?',(day,lane)).fetchone():return
  seen={discovery.key(r['artist'],r['title']) for r in c.execute('SELECT t.artist,t.title FROM daily_candidates d JOIN tracks t ON t.id=d.track_id WHERE d.lane=?',(lane,))}
  seen|={discovery.key(r['artist'],r['title']) for r in c.execute('SELECT artist,title FROM tracks WHERE rating=-1')}
  if lane=='style':seen|={discovery.key(r['artist'],r['title']) for r in c.execute('SELECT artist,title FROM tracks WHERE rating<>0')}
 chosen=choose(pool,seen)
 for pos,t in enumerate(chosen):
  t=match_preview(t) if not t.get('deezer_id') else t;tid=register(t)
  with app.db() as c:c.execute('INSERT OR IGNORE INTO daily_candidates(day,lane,track_id,position,reason) VALUES (?,?,?,?,?)',(day,lane,tid,pos,t['reason']))
def style_pool():
 candidates,tracks,policy=discovery.collect()
 # Keep 80/20 discovery while retaining enough candidates for filtering already reviewed songs.
 familiar=sorted((t for t in candidates if t['kind']=='familiar'),key=lambda t:-t['score'])
 exploration=sorted((t for t in candidates if t['kind']=='exploration'),key=lambda t:-t['score'])
 result=[]
 while familiar or exploration:
  for _ in range(4):
   if familiar:result.append(familiar.pop(0))
  if exploration:result.append(exploration.pop(0))
 return result
def top_pool():
 with app.db() as c:charts=[dict(r) for r in c.execute('SELECT * FROM chart_snapshots WHERE error IS NULL')]
 result=[]
 for rank in range(1,21):
  for chart in charts:
   for t in json.loads(chart['tracks']):
    if t['rank']==rank:result.append({**t,'reason':f"Top {rank} · {chart['region'].upper()} · {chart['edition']}"})
 return result
def portuguese_pool(day):
 artists=sorted(PT_ARTISTS,key=lambda a:hashlib.sha256((day+a).encode()).hexdigest())[:10];pool=[]
 for artist in artists:
  try:
   data=discovery.fetch('search/artist?'+urllib.parse.urlencode({'q':artist,'limit':5}))
   record=next((a for a in data.get('data',[]) if discovery.artist_key(a['name'])==discovery.artist_key(artist)),None)
   if not record:continue
   for t in discovery.fetch('artist/'+str(record['id'])+'/top?limit=15').get('data',[]):
    if discovery.valid(t) and discovery.artist_key(t['artist']['name'])==discovery.artist_key(artist):pool.append({'artist':t['artist']['name'],'title':t['title'],'deezer_id':int(t['id']),'reason':'Descoberta de música portuguesa · seleção de artistas, ajustada pelas tuas aprovações nesta lista.'})
  except (OSError,ValueError,KeyError):continue
 # Equal opportunity for every artist; feedback affects ordering without conflating the style lane.
 with app.db() as c:
  weights={r['artist']:r['weight'] for r in c.execute("SELECT t.artist,SUM(CASE WHEN d.decision>0 THEN d.decision WHEN d.decision<0 THEN -2 ELSE 0 END) weight FROM daily_candidates d JOIN tracks t ON t.id=d.track_id WHERE d.lane='portuguese' GROUP BY t.artist")}
 return sorted(pool,key=lambda t:-weights.get(t['artist'],0))
def view(selected=None):
 day=today()
 with app.db() as c:
  days=[r[0] for r in c.execute('SELECT DISTINCT day FROM daily_candidates ORDER BY day DESC')]
  if selected and selected not in ('pending','all') and selected not in days:raise ValueError('Seleção inexistente.')
  latest=selected or (days[0] if days else day)
  query='SELECT d.*,t.artist,t.title,t.path,p.deezer_id FROM daily_candidates d JOIN tracks t ON t.id=d.track_id LEFT JOIN preview_catalog p ON p.track_id=t.id '
  rows=[dict(r) for r in c.execute(query+('WHERE d.decision=0 ORDER BY d.day DESC,d.lane,d.position' if selected=='pending' else 'ORDER BY d.day DESC,d.lane,d.position' if selected=='all' else 'WHERE d.day=? ORDER BY d.lane,d.position'),() if selected in ('pending','all') else (latest,))]
  charts=[dict(r) for r in c.execute('SELECT region,edition,url,fetched,error FROM chart_snapshots')]
 for r in rows:r['available']=bool(r.pop('path'))
 return {'days':days,'day':latest,'today':day,'tracks':rows,'charts':charts,'target':10,'backup':'Pendente: aguarda o disco de rede.'}
def main():
 playlists.init();day=today();refresh_charts()
 for lane,make in [('style',style_pool),('global',top_pool),('portuguese',lambda:portuguese_pool(day))]:
  with app.db() as c:existing=c.execute('SELECT count(*) FROM daily_candidates WHERE day=? AND lane=?',(day,lane)).fetchone()[0]
  if existing:continue
  try:store(day,lane,make())
  except (OSError,ValueError,KeyError):
   with app.db() as c:app.event(c,'daily_source_unavailable',{'lane':lane})
 with app.db() as c:members=[r[0] for r in c.execute('SELECT id FROM users WHERE active=1 AND id<>1')]
 for member in members:
  token=accounts.CURRENT.set(member)
  try:store(day,'style',style_pool())
  except (OSError,ValueError,KeyError):pass
  finally:accounts.CURRENT.reset(token)
 playlists.reconcile()
 print(json.dumps({'day':day,'counts':{lane:sum(t['lane']==lane for t in view()['tracks']) for lane in app.LANES}}))
if __name__=='__main__':main()
