"""First discovery batch: explainable artist preferences and catalog relations, no downloads."""
import collections,json,re,time,urllib.request
import app
from catalog_previews import artist_key,title_key

def fetch(path):
    req=urllib.request.Request('https://api.deezer.com/'+path,headers={'User-Agent':'PersonalMediaCenter/1.0'})
    with urllib.request.urlopen(req,timeout=20) as r: data=json.load(r)
    if data.get('error'): raise ValueError('Catalog unavailable')
    time.sleep(.2)
    return data

def key(artist,title):
    title=re.sub(r'\s*\([^)]*\)|\s*-\s*[^-]*(?:remaster|radio edit|album version)[^-]*$', '', title, flags=re.I)
    return artist_key(artist)+'|'+title_key(title)

def valid(t):
    version=(t.get('title_version','')+' '+' '.join(re.findall(r'\(([^)]*)\)',t.get('title','')))).casefold()
    return bool(t.get('readable') and t.get('preview')) and not any(v in version for v in ['live','remix','rmx','acoustic','karaoke','instrumental','tribute'])

def select(candidates,known,limit=30,exploration_percent=20):
    # Reserve exploration positions; keep artist variety and reject known songs in every rating state.
    selected=[];seen=set(known);counts=collections.Counter()
    exploration=round(limit*exploration_percent/100)
    for kind,budget in [('familiar',limit-exploration),('exploration',exploration)]:
        if budget<=0: continue
        pool=sorted((c for c in candidates if c['kind']==kind),key=lambda c:(-c['score'],c['artist'],c['title']))
        used=0
        for c in pool:
            k=key(c['artist'],c['title']);a=artist_key(c['artist'])
            if k in seen or counts[a]>=3: continue
            selected.append(c);seen.add(k);counts[a]+=1;used+=1
            if used>=budget: break
    return selected

def collect():
    app.init()
    with app.db() as con:
        tracks=[dict(r) for r in con.execute('SELECT t.*,p.deezer_id FROM tracks t LEFT JOIN preview_catalog p ON t.id=p.track_id')]
        previous={r['track_id'] for r in con.execute('SELECT track_id FROM recommendations')}
        policy=json.loads(con.execute("SELECT value FROM settings WHERE key='policy'").fetchone()[0])
    import accounts
    if accounts.uid()!=1:tracks=accounts.overlay_tracks(tracks)
    groups=collections.defaultdict(list)
    for t in tracks: groups[artist_key(t['artist'])].append(t)
    seeds=[]
    for a,items in groups.items():
        pos=[t for t in items if t['rating']>0];negative=sum(t['rating']==-1 for t in items)
        if len(pos)<2: continue
        love=sum(t['rating']==2 for t in pos);score=(len(pos)+2*love)/(len(pos)+negative+2)
        anchors=sorted((t for t in pos if t['deezer_id']),key=lambda t:-t['rating'])
        if anchors: seeds.append({'key':a,'name':anchors[0]['artist'],'anchor':anchors[0],'score':score,'positive':len(pos),'negative':negative,'loves':love})
    seeds=sorted(seeds,key=lambda s:-s['score'])[:10]
    candidates=[];related={};errors=0
    for seed in seeds:
        try:
            track=fetch('track/'+str(seed['anchor']['deezer_id']));aid=int(track['artist']['id'])
            top=fetch('artist/'+str(aid)+'/top?limit=30').get('data',[])
            reason=f"Classificaste {seed['positive']} músicas de {seed['name']} positivamente, incluindo {seed['loves']} como Adoro. Uma faixa diferente desse artista para validares."
            if seed['negative']: reason+=' Como também rejeitaste outras faixas, esta escolha ainda precisa da tua avaliação.'
            for t in top:
                if valid(t) and artist_key(t['artist']['name'])==seed['key']: candidates.append({'artist':t['artist']['name'],'title':t['title'],'deezer_id':int(t['id']),'kind':'familiar','score':seed['score']+min(t.get('rank',0),1000000)/10000000,'reason':reason})
            for artist in fetch('artist/'+str(aid)+'/related?limit=4').get('data',[]):
                if artist_key(artist['name']) in groups: continue
                rid=int(artist['id'])
                if rid not in related or related[rid]['score']<seed['score']:
                    related[rid]={'artist':artist,'score':seed['score'],'source':seed['name']}
        except (OSError,ValueError,KeyError): errors+=1
    for relation in sorted(related.values(),key=lambda r:-r['score'])[:10]:
        try:
            for t in fetch('artist/'+str(relation['artist']['id'])+'/top?limit=5').get('data',[]):
                if valid(t) and artist_key(t['artist']['name']) not in groups: candidates.append({'artist':t['artist']['name'],'title':t['title'],'deezer_id':int(t['id']),'kind':'exploration','score':relation['score']*.6+min(t.get('rank',0),1000000)/10000000,'reason':f"Exploração: a Deezer relaciona {t['artist']['name']} com {relation['source']}, de quem gostaste. É uma hipótese para testares, sem assumir que vais gostar."})
        except (OSError,ValueError,KeyError): errors+=1
    return candidates,tracks,policy

def main():
    candidates,tracks,policy=collect()
    with app.db() as con: previous={r[0] for r in con.execute("SELECT track_id FROM recommendations")}
    selected=select(candidates,{key(t['artist'],t['title']) for t in tracks if t['id'] not in previous or t['rating']!=0},exploration_percent=policy['exploration_percent'])
    if not selected: raise RuntimeError('No new candidates; previous recommendations preserved')
    now=int(time.time())
    with app.db() as con:
        con.execute('DELETE FROM recommendations')
        selected_ids=set()
        for position,c in enumerate(selected):
            track_key=app.norm(c['artist'])+'|'+app.norm(c['title'])
            con.execute('INSERT OR IGNORE INTO tracks(artist,title,track_key,updated) VALUES (?,?,?,?)',(c['artist'],c['title'],track_key,now))
            tid=con.execute('SELECT id FROM tracks WHERE track_key=?',(track_key,)).fetchone()[0]
            con.execute('INSERT OR REPLACE INTO preview_catalog VALUES (?,?,?,?,?)',(tid,c['deezer_id'],c['artist'],c['title'],now))
            selected_ids.add(tid)
            con.execute('INSERT INTO recommendations VALUES (?,?,?,?,?,?)',(tid,position,c['score'],c['reason'],c['kind'],now))
        for tid in previous-selected_ids:
            row=con.execute('SELECT rating,seed,path FROM tracks WHERE id=?',(tid,)).fetchone()
            if row and row['rating']==0 and row['seed']==0 and row['path'] is None:
                con.execute('DELETE FROM preview_catalog WHERE track_id=?',(tid,))
                con.execute('DELETE FROM tracks WHERE id=?',(tid,))
        report={'created':now,'selected':len(selected),'familiar':sum(c['kind']=='familiar' for c in selected),'exploration':sum(c['kind']=='exploration' for c in selected),'catalog_errors':errors,'method':'artist_preferences_and_catalog_relations','sonic_analysis':False}
        con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('discovery_report',json.dumps(report)))
    print(json.dumps(report))

if __name__=='__main__':main()
