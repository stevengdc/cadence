import json,unittest,unittest.mock as mock,http.cookiejar,urllib.request
import app,accounts,operations,playlists,test_app
class AccountTests(unittest.TestCase):
 setUp=test_app.ProfileTests.setUp
 tearDown=test_app.ProfileTests.tearDown
 request=test_app.ProfileTests.request
 login=test_app.ProfileTests.login
 def member(self):
  accounts.init()
  with app.db() as c:c.execute("INSERT INTO users(id,username,name,password,role) VALUES(2,'wife','Wife',?,'member')",(accounts.hash_password('password123'),))
 def test_session_revoked_when_disabled(self):
  self.member();token=accounts.login({'username':'wife','password':'password123'})
  self.assertTrue(accounts.authenticate(token));accounts.CURRENT.set(1)
  accounts.update({'id':2,'active':0})
  self.assertFalse(accounts.authenticate(token));accounts.CURRENT.set(1)
 def test_member_cannot_administer(self):
  self.member();self.request('/api/login',{'username':'wife','password':'password123'})
  self.assertEqual(self.request('/api/users')[0],403)
  self.assertEqual(self.request('/api/policy',{'concurrency':5})[0],403)
  self.assertEqual(self.request('/api/automations',{'id':'search','enabled':False,'seconds':60})[0],403)
  self.assertEqual(self.request('/api/account',{'id':1,'name':'Hacked'})[0],403)
 def test_personal_rating_isolated(self):
  self.member();self.login();self.request('/api/rating',{'id':1,'rating':2})
  self.request('/api/login',{'username':'wife','password':'password123'})
  self.assertEqual(self.request('/api/tracks')[1][0]['rating'],0)
  self.request('/api/rating',{'id':1,'rating':-1})
  self.assertEqual(self.request('/api/tracks')[1][0]['rating'],-1)
  self.login();self.assertEqual(self.request('/api/tracks')[1][0]['rating'],2)
 def test_not_today_does_not_rate_or_approve(self):
  self.login();self.request('/api/rating',{'id':1,'rating':2})
  self.assertEqual(self.request('/api/defer',{'id':1})[0],200)
  rows=self.request('/api/tracks')[1]
  self.assertEqual(rows[0]['rating'],2);self.assertTrue(rows[0]['deferred_until'])
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM acquisition_queue').fetchone()[0],0)
 def test_password_change_invalidates_sessions(self):
  self.login();password=(app.ROOT/'admin-password.txt').read_text().strip()
  self.assertEqual(self.request('/api/account',{'current_password':password,'password':'newpassword1'})[0],200)
  self.assertEqual(self.request('/api/me')[0],401)
  self.assertEqual(self.request('/api/login',{'password':'newpassword1'})[0],200)
 def test_theme_and_logout(self):
  self.login();self.assertEqual(self.request('/api/account',{'theme':'light','accent':'purple'})[0],200)
  self.assertEqual(self.request('/api/me')[1]['theme'],'light')
  self.request('/api/logout',{});self.assertEqual(self.request('/api/me')[0],401)
 def test_task_ownership(self):
  self.member();self.login();self.request('/api/tasks',{'title':'Admin task','due':'2026-10-20'})
  self.request('/api/login',{'username':'wife','password':'password123'})
  self.assertEqual(self.request('/api/tasks')[1],[])
  tasks=self.request('/api/tasks',{'title':'My task'})[1];self.assertEqual(len(tasks),1)
 def test_schedule_validation(self):
  self.login()
  self.assertEqual(self.request('/api/automations',{'id':'../../bad','enabled':True})[0],400)
  self.assertEqual(self.request('/api/automations',{'id':'daily','enabled':True,'time':'25:99'})[0],400)
  self.assertEqual(self.request('/api/automations',{'id':'daily','enabled':False,'time':'08:30'})[0],200)
  self.assertEqual(json.loads((app.ROOT/'schedules.json').read_text())['daily']['time'],'08:30')
 def test_playlist_owner_filter(self):
  self.member();accounts.CURRENT.set(2)
  with app.db() as c:c.execute("INSERT INTO owned_playlists VALUES('wife-playlist',2)")
  with mock.patch.object(playlists,'call',return_value={'Items':[{'Id':'admin-playlist','Name':'Style'},{'Id':'wife-playlist','Name':'Style'}]}):
   self.assertEqual([p['id'] for p in playlists.playlists()],['wife-playlist'])
  accounts.CURRENT.set(1)
 def test_emby_account_creation(self):
  self.login();accounts.CURRENT.set(1)
  with mock.patch.object(operations,'emby',side_effect=[{'Id':'new-emby'},{}]) as emby:
   result=accounts.create({'username':'new-user','name':'New user','password':'password123'})
   self.assertTrue(result['ok']);self.assertEqual(emby.call_args_list[0].args[0],'Users/New')
  with app.db() as c:r=c.execute("SELECT emby_id,role FROM users WHERE username='new-user'").fetchone()
  self.assertEqual(tuple(r),('new-emby','member'))
 def test_personal_daily_approval_keeps_primary_taste(self):
  self.member();playlists.init()
  with app.db() as c:
   c.execute('UPDATE tracks SET rating=2 WHERE id=1')
   c.execute("INSERT INTO daily_candidates VALUES('2026-10-09','style',1,0,'Primary',2)")
   c.execute("INSERT INTO user_candidates VALUES(2,'2026-10-09','style',1,0,'Personal')")
   c.execute("INSERT INTO user_lanes VALUES(2,'style','personal-style')")
  accounts.CURRENT.set(2)
  with mock.patch.object(playlists,'ensure_lanes'),mock.patch.object(playlists,'add',return_value={'ready':False}) as add:
   playlists.approve({'day':'2026-10-09','lane':'style','id':1,'decision':1})
   add.assert_called_once_with('personal-style',1)
  with app.db() as c:
   self.assertEqual(c.execute('SELECT rating FROM tracks WHERE id=1').fetchone()[0],2)
   self.assertEqual(c.execute('SELECT decision FROM daily_candidates').fetchone()[0],2)
   self.assertEqual(c.execute('SELECT rating FROM user_ratings WHERE user_id=2').fetchone()[0],1)
  accounts.CURRENT.set(1)
if __name__=='__main__':unittest.main()
