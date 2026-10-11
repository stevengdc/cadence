import http.cookiejar, json, pathlib, tempfile, threading, unittest, urllib.request, urllib.error
import app

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); app.ROOT=pathlib.Path(self.tmp.name)/'state'
        app.MEDIA=pathlib.Path(self.tmp.name)/'music'; app.MEDIA.mkdir(); app.init()
        self.csv=pathlib.Path(self.tmp.name)/'seed.csv'; self.csv.write_text('artist,title\nArtist,Song\nArtist,Song (Live)\n')
        app.import_csv(self.csv)
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def request(self,path,data=None,origin=None):
        headers={'Origin':origin or self.base,'Content-Type':'application/json'}
        req=urllib.request.Request(self.base+path,headers=headers,data=None if data is None else json.dumps(data).encode())
        try:
            with self.client.open(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            with e:return e.code,json.load(e)
    def login(self):
        self.assertEqual(self.request('/api/login',{'password':(app.ROOT/'admin-password.txt').read_text()})[0],200)
    def test_auth_and_origin(self):
        self.assertEqual(self.request('/api/status')[0],401)
        self.assertEqual(self.request('/api/login',{'password':'wrong'})[0],401)
        self.login()
        self.assertEqual(self.request('/api/rating',{'id':1,'rating':2},'http://other.example')[0],403)
    def test_acquisition_cannot_be_enabled(self):
        self.login()
        self.assertEqual(self.request('/api/policy',{'downloads_enabled':True})[0],400)
        self.assertEqual(self.request('/api/policy',{'mode':'autonomous'})[0],400)
        self.assertFalse(self.request('/api/status')[1]['policy']['downloads_enabled'])
    def test_ratings_survive_import_and_restart(self):
        self.login();self.assertEqual(self.request('/api/rating',{'id':1,'rating':2})[0],200)
        app.import_csv(self.csv);app.init()
        tracks=self.request('/api/tracks')[1]
        self.assertEqual(len(tracks),2)
        self.assertEqual(next(t for t in tracks if t['id']==1)['rating'],2)
    def test_invalid_limits_leave_previous_policy(self):
        self.login();before=self.request('/api/status')[1]['policy']
        self.assertEqual(self.request('/api/policy',{'retry_minutes':9999})[0],400)
        self.assertEqual(self.request('/api/status')[1]['policy'],before)
        self.assertEqual(self.request('/api/policy',{'retry_minutes':60})[0],200)
    def test_invalid_ratings_and_injection_search(self):
        self.login()
        self.assertEqual(self.request('/api/rating',{'id':1,'rating':99})[0],400)
        self.assertEqual(self.request('/api/tracks?search=%27%20OR%201%3D1')[1],[])
    def test_sample_auth_range_and_missing(self):
        self.assertEqual(self.request('/api/sample/1')[0],401)
        self.login(); self.assertEqual(self.request('/api/sample/1')[0],404)
        source=app.MEDIA/'song.mp3';source.write_bytes(b'original')
        with app.db() as con: con.execute('UPDATE tracks SET path=? WHERE id=1',(str(source),))
        target=app.sample_path({'id':1,'path':str(source)});target.parent.mkdir()
        target.write_bytes(b'0123456789')
        self.assertTrue(self.request('/api/tracks')[1][0]['preview'])
        req=urllib.request.Request(self.base+'/api/sample/1',headers={'Range':'bytes=2-5'})
        with self.client.open(req) as r:
            self.assertEqual(r.status,206);self.assertEqual(r.read(),b'2345')
            self.assertEqual(r.headers['Content-Range'],'bytes 2-5/10')
        with self.client.open(urllib.request.Request(self.base+'/api/sample/1',method='HEAD')) as r:
            self.assertEqual(r.headers['Content-Length'],'10');self.assertEqual(r.read(),b'')
        self.assertEqual(self.request('/api/sample/999')[0],404)
    def test_sample_never_serves_paths_outside_music(self):
        self.login();outside=app.ROOT/'secret.mp3';outside.write_bytes(b'secret')
        with app.db() as con: con.execute('UPDATE tracks SET path=? WHERE id=1',(str(outside),))
        self.assertEqual(self.request('/api/sample/1')[0],404)

if __name__=='__main__':unittest.main()
