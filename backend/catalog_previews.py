"""Match missing previews to Deezer catalog IDs, never save remote audio or expiring URLs."""
import argparse,json,re,time,urllib.request,urllib.parse
import app

def artist_key(name):
    key=app.norm(name)
    return {'googoodolls':'thegoogoodolls','alicedeejay':'alicedj'}.get(key,key)

def title_key(title):
    title=re.sub(r'\s*\((?:feat\.?|featuring)\s+[^)]*\)', '', title, flags=re.I)
    return app.norm(title.replace('&',' and '))

def choose(track, candidates):
    matches=[]
    for c in candidates:
        if artist_key(c.get('artist',{}).get('name','')) != artist_key(track['artist']): continue
        if title_key(track['title']) not in {title_key(c.get('title','')),title_key(c.get('title_short',''))}: continue
        if not c.get('preview') or not c.get('readable'): continue
        version=c.get('title_version','').casefold()
        if any(w in version for w in ['live','remix','acoustic','karaoke','instrumental','tribute']):
            if app.norm(c.get('title','')) != app.norm(track['title']): continue
        matches.append(c)
    return max(matches,key=lambda c:(app.norm(c.get('title',''))==app.norm(track['title']),not bool(c.get('title_version')),c.get('rank',0)),default=None)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--missing-only',action='store_true');args=parser.parse_args()
    app.init()
    with app.db() as con:
        tracks=[dict(r) for r in con.execute('SELECT id,artist,title,path FROM tracks WHERE path IS NULL'+(' AND id NOT IN (SELECT track_id FROM preview_catalog)' if args.missing_only else ''))]
    found=errors=0; missing=[]
    for i,t in enumerate(tracks):
        query=urllib.parse.urlencode({'q':t['artist']+' '+t['title'],'limit':100})
        match=None
        try:
            req=urllib.request.Request('https://api.deezer.com/search?'+query,headers={'User-Agent':'PersonalMediaCenter/1.0'})
            with urllib.request.urlopen(req,timeout=20) as r: result=json.load(r)
            if result.get('error'): raise ValueError('catalog error')
            match=choose(t,result.get('data',[]))
        except (OSError,ValueError): errors+=1
        if match:
            with app.db() as con:
                con.execute('INSERT OR REPLACE INTO preview_catalog VALUES (?,?,?,?,?)',(t['id'],int(match['id']),match['artist']['name'],match['title'],int(time.time())))
            found+=1
        else: missing.append({'id':t['id'],'artist':t['artist'],'title':t['title']})
        if (i+1)%40==0: print(json.dumps({'checked':i+1,'found':found,'errors':errors}),flush=True)
        time.sleep(0.35)
    (app.ROOT/'preview-missing.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2))
    print(json.dumps({'checked':len(tracks),'found':found,'missing':len(missing),'errors':errors}),flush=True)

if __name__=='__main__': main()
