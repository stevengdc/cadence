import unittest
from discovery import select,key
class DiscoveryTests(unittest.TestCase):
    def candidates(self):
        return [{'artist':str(a),'title':str(t),'score':10-a,'kind':kind} for kind in ['familiar','exploration'] for a in range(12) for t in range(10)]
    def test_excludes_known_rejected_songs_and_remaster_duplicates(self):
        rows=[{'artist':'Artist','title':'Song (2011 Remastered)','score':3,'kind':'familiar'},{'artist':'Artist','title':'Other','score':2,'kind':'familiar'}]
        self.assertEqual([r['title'] for r in select(rows,{key('Artist','Song')},limit=2,exploration_percent=0)],['Other'])
    def test_limits_diversity_and_exploration_quota(self):
        # Different artists for exploration, otherwise familiar results would exhaust the same artist cap.
        rows=self.candidates()
        for r in rows:
            if r['kind']=='exploration':r['artist']='new'+r['artist']
        result=select(rows,set());self.assertEqual(len(result),30)
        self.assertEqual(sum(r['kind']=='exploration' for r in result),6)
        self.assertEqual(len({key(r['artist'],r['title']) for r in result}),30)
        for a in {r['artist'] for r in result}:self.assertLessEqual(sum(r['artist']==a for r in result),3)
    def test_zero_exploration_and_empty_pool(self):
        self.assertFalse(any(r['kind']=='exploration' for r in select(self.candidates(),set(),exploration_percent=0)))
        self.assertEqual(select([],set()),[])

class VersionTests(unittest.TestCase):
    def test_live_in_title_rejected_without_version_metadata(self):
        from discovery import valid
        self.assertFalse(valid({'readable':True,'preview':'yes','title':'Training Season (Live from the Royal Albert Hall)','title_version':''}))
        self.assertTrue(valid({'readable':True,'preview':'yes','title':'Live Forever','title_version':''}))
    def test_alternate_edits_not_recommended_as_new_song(self):
        self.assertEqual(key('Dire Straits','Money For Nothing (Edit)'),key('Dire Straits','Money for Nothing'))
        self.assertEqual(key('Evanescence','My Immortal (Band Version)'),key('Evanescence','My Immortal'))
