import unittest
from catalog_previews import choose
class MatchingTests(unittest.TestCase):
    def candidate(self,artist='Artist',title='Song',version=''):
        return {'id':1,'artist':{'name':artist},'title':title+(' ('+version+')' if version else ''),'title_short':title,'title_version':version,'preview':'available','readable':True}
    def test_cover_artist_and_unrequested_remix_rejected(self):
        t={'artist':'Artist','title':'Song'}
        self.assertIsNone(choose(t,[self.candidate(artist='Cover Artist'),self.candidate(version='Remix'),self.candidate(version='Live')]))
    def test_original_preferred_and_explicit_version_allowed(self):
        original=self.candidate(); remaster=self.candidate(version='Remastered')
        self.assertIs(choose({'artist':'Artist','title':'Song'},[remaster,original]),original)
        remix=self.candidate(version='Remix')
        self.assertIs(choose({'artist':'Artist','title':'Song (Remix)'},[remix]),remix)
    def test_unavailable_preview_rejected(self):
        c=self.candidate();c['preview']=''
        self.assertIsNone(choose({'artist':'Artist','title':'Song'},[c]))
