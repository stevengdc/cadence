import pathlib,tempfile,unittest,subprocess,math,json
import loudness,app
from mutagen.id3 import ID3,TXXX
class LoudnessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'test.mp3'
 def tearDown(self):self.tmp.cleanup()
 def make(self,volume=1):
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=1000:duration=8','-af','volume='+str(volume),'-c:a','libmp3lame','-b:a','320k',str(self.path)],check=True)
 def test_tags_preserve_stream_and_replace_conflicts(self):
  self.make();tags=ID3(self.path);tags.add(TXXX(encoding=3,desc='R128_TRACK_GAIN',text=['200']));tags.save()
  before=loudness.stream_hash(self.path);data=loudness.prepare(self.path);self.assertEqual(before,loudness.stream_hash(self.path))
  tags=ID3(self.path);self.assertIn('TXXX:REPLAYGAIN_TRACK_GAIN',tags);self.assertNotIn('TXXX:R128_TRACK_GAIN',tags)
  self.assertLessEqual(data['true_peak']+data['gain_db'],-.99)
  self.assertAlmostEqual(data['result_lufs'],-18,delta=.02)
 def test_quiet_and_loud_tracks_get_opposite_corrections(self):
  self.make(.1);quiet=loudness.measure(self.path);self.path.unlink();self.make(6);loud=loudness.measure(self.path)
  self.assertGreater(quiet['gain_db'],loud['gain_db']);self.assertLess(loud['gain_db'],0)
 def test_silence_requires_review(self):
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','8','-c:a','libmp3lame','-b:a','320k',str(self.path)],check=True)
  with self.assertRaises(ValueError):loudness.measure(self.path)
 def test_flac_existing_gain_tags_are_replaced(self):
  from mutagen.flac import FLAC
  path=self.path.with_suffix('.flac')
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=8',str(path)],check=True)
  tags=FLAC(path);tags['REPLAYGAIN_TRACK_GAIN']=['-4 dB'];tags.save()
  before=loudness.stream_hash(path);loudness.prepare(path)
  self.assertEqual(loudness.stream_hash(path),before)
  self.assertIn('replaygain_track_gain',FLAC(path))
if __name__=='__main__':unittest.main()
