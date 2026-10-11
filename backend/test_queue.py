import unittest
from test_app import ProfileTests
class QueueTests(ProfileTests):
    def test_queue_only_positive_missing_and_unique(self):
        self.login();self.request('/api/rating',{'id':1,'rating':2})
        first=self.request('/api/queue')[1];second=self.request('/api/queue')[1]
        self.assertEqual([r['id'] for r in first['tracks']],[1])
        self.assertEqual(len(second['tracks']),1)
        self.assertFalse(first['executor_enabled'])
    def test_approval_rejection_and_lane(self):
        self.login();self.request('/api/rating',{'id':1,'rating':1});self.request('/api/queue')
        self.assertEqual(self.request('/api/queue',{'id':1,'action':'approve'})[0],200)
        self.assertEqual(self.request('/api/queue',{'id':1,'action':'lane','lane':'portuguese'})[0],200)
        row=self.request('/api/queue')[1]['tracks'][0]
        self.assertEqual((row['state'],row['lane']),('approved','portuguese'))
        self.request('/api/rating',{'id':1,'rating':-1})
        self.assertEqual(self.request('/api/queue',{'id':1,'action':'approve'})[0],409)
        self.assertTrue(self.request('/api/queue')[1]['tracks'][0]['blocked'])
    def test_queue_auth_and_invalid_lane(self):
        self.assertEqual(self.request('/api/queue')[0],401)
        self.login();self.request('/api/rating',{'id':1,'rating':1});self.request('/api/queue')
        self.assertEqual(self.request('/api/queue',{'id':1,'action':'lane','lane':'invalid'})[0],400)
if __name__=='__main__':unittest.main()
