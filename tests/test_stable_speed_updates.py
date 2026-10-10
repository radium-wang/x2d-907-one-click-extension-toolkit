"""Numeric stable update isolation; no network or camera requests."""
import io,json,unittest
import app_updates as updates
from payload_support import requires_payloads
class StableUpdates(unittest.TestCase):
 def release(self,platform):
  name=updates.ARCHIVE_BASE+'-'+('macOS-Universal' if platform=='mac' else 'Windows-x64')+'-0.4.17.zip'
  return dict(tag_name='v0.4.17',draft=False,prerelease=False,assets=[dict(name=name,size=123,digest='sha256:'+'a'*64,browser_download_url='https://github.com/'+updates.REPO+'/releases/download/v0.4.17/'+name)])
 def test_original_stable_detects_new_version_and_beta_does_not(self):
  self.assertEqual(updates.REPO,'radium-wang/x2d-907-one-click-extension-toolkit')
  for platform in ('win','mac'):
   opener=lambda url:io.BytesIO(json.dumps(self.release(platform)).encode())
   self.assertEqual(updates.latest('0.4.12',platform,opener)['version'],'0.4.17')
   for current in ('0.4.17','0.5.0','0.5.1'):
    self.assertIsNone(updates.latest(current,platform,opener))

class StableRecoveryCatalog(unittest.TestCase):
 @requires_payloads
 def test_original_0412_all_masks_languages_and_tamper_rejection(self):
  import copy
  import x2d_play_software as app
  if not (app.O/'previous-bundle-0.4.12.json').exists():self.skipTest('Exact original stable recovery input required')
  baseline=json.loads((app.O/'previous-bundle-0.4.12.json').read_bytes())
  for language in ('zh','zh-Hant','en'):
   for mask in range(1,8):
    selected=app.select_features(app.apply_ui_language(baseline,language),[f for i,f in enumerate(app.FEATURES) if mask&(1<<i)])
    self.assertTrue(app.recognized_bundle(selected),(language,mask))
    bad=copy.deepcopy(selected);bad['files'][0]['sha256']='0'*64
    self.assertFalse(app.recognized_bundle(bad))
