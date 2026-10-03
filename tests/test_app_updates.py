import hashlib
import io
import json
import plistlib
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch
import app_updates as u


class Updates(unittest.TestCase):
    def release(self, new='0.4.1', platform='win'):
        name=u.BASE+'-'+('Windows-x64' if platform=='win' else 'macOS-Universal')+'-'+new+'.zip'
        return dict(tag_name='v'+new,draft=False,prerelease=False,assets=[dict(name=name,
            size=123, digest='sha256:'+'a'*64,
            browser_download_url='https://github.com/'+u.REPO+'/releases/download/v'+new+'/'+name)])

    def opener(self, obj): return lambda url: io.BytesIO(json.dumps(obj).encode())

    def test_versions_use_numeric_order_and_skip_same_older(self):
        self.assertIsNone(u.latest('0.4.1','win',self.opener(self.release())))
        self.assertIsNone(u.latest('1.0.0','win',self.opener(self.release())))
        self.assertEqual(u.latest('0.4.0','win',self.opener(self.release('0.10.0')))['version'],'0.10.0')
        for invalid in ('v1','1.0.0-beta','../1.2.3','1.2.3\n',''):
            with self.assertRaises(u.UpdateError):u.version(invalid)

    def test_no_release_and_rate_limit(self):
        def fail(code):
            def open(url):raise urllib.error.HTTPError(url,code,'error',None,None)
            return open
        self.assertIsNone(u.latest('0.4.0','win',fail(404)))
        with self.assertRaisesRegex(u.UpdateError,'暂时受限'):u.latest('0.4.0','win',fail(403))

    def test_only_exact_project_platform_asset_with_digest(self):
        for mutate in (lambda r:r.update(prerelease=True),
                       lambda r:r['assets'][0].update(digest=None),
                       lambda r:r['assets'][0].update(size=True),
                       lambda r:r['assets'][0].update(browser_download_url='https://example.com/update.zip'),
                       lambda r:r['assets'].append(r['assets'][0]),
                       lambda r:r['assets'][0].update(name='other.zip')):
            release=self.release();mutate(release)
            with self.assertRaises(u.UpdateError):u.latest('0.4.0','win',self.opener(release))
        info=u.latest('0.4.0','mac',self.opener(self.release(platform='mac')))
        self.assertIn('macOS-Universal',info['url'])
        self.assertIn('%',info['url'])

    def test_partial_tampered_and_oversized_downloads_never_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'download.zip';data=b'good'
            info=dict(url='unused',size=len(data),sha256=hashlib.sha256(data).hexdigest())
            u.download(info,p,lambda *a,**k:None,lambda url:io.BytesIO(data))
            self.assertEqual(p.read_bytes(),data);p.unlink()
            for bad in (b'bad',b'evil',b'too big'):
                with self.assertRaises(u.UpdateError):u.download(info,p,lambda *a,**k:None,lambda url:io.BytesIO(bad))
                self.assertFalse(p.exists())

    def archive(self, directory, entries):
        p=directory/'update.zip'
        with zipfile.ZipFile(p,'w') as z:
            for name,data in entries:z.writestr(name,data)
        return p

    def test_zip_traversal_duplicate_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            for name in ('../outside','/outside',u.BASE+'-Windows-x64/../outside',u.BASE+'-Windows-x64\\outside', 'wrong/a'):
                with self.assertRaises(u.UpdateError):u.extract(self.archive(d,[(name,b'x')]),d/'stage','win')
            name=u.BASE+'-Windows-x64/test'
            with self.assertRaises(u.UpdateError):u.extract(self.archive(d,[(name,b'x'),(name.upper(),b'x')]),d/'stage','win')
            link=zipfile.ZipInfo(name);link.external_attr=0o120777<<16
            with self.assertRaises(u.UpdateError):u.extract(self.archive(d,[(link,b'/tmp')]),d/'stage','win')
            self.assertFalse((d.parent/'outside').exists())

    def fake_app(self, d, ver):
        d.mkdir()
        (d/'版本与校验.json').write_text(json.dumps(dict(version=ver)))
        for name in (u.BASE+'.exe','runtime/pythonw.exe','windows_app.py','app_updates.py','native-package/speed-bundle.json'):
            p=d/name;p.parent.mkdir(exist_ok=True);p.write_bytes(b'fixture')
        return d

    def test_safe_swap_and_rollback_preserve_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);target=self.fake_app(d/'installed','0.4.0');new=self.fake_app(d/'staged','0.4.1');backup=d/'previous'
            u.swap(new,target,backup,'win','0.4.1')
            self.assertEqual(u.validate_app(target,'win'),'0.4.1')
            self.assertEqual(u.validate_app(backup,'win'),'0.4.0')
            self.assertFalse(new.exists())
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);target=self.fake_app(d/'installed','0.4.0');new=self.fake_app(d/'staged','0.4.1');backup=d/'previous'
            original=Path.rename
            def rename(path,to):
                if path==new:raise PermissionError('locked')
                return original(path,to)
            with patch.object(Path,'rename',rename),self.assertRaises(PermissionError):u.swap(new,target,backup,'win','0.4.1')
            self.assertEqual(u.validate_app(target,'win'),'0.4.0');self.assertTrue(new.exists());self.assertFalse(backup.exists())

    def test_mismatched_package_cannot_replace_target(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);target=self.fake_app(d/'installed','0.4.0');new=self.fake_app(d/'staged','0.4.2')
            with self.assertRaises(u.UpdateError):u.swap(new,target,d/'previous','win','0.4.1')
            self.assertEqual(u.validate_app(target,'win'),'0.4.0')

    def test_prepare_change_in_release_fails_before_any_files(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(u,'latest',return_value=None):
            d=Path(folder)
            with self.assertRaises(u.UpdateError):u.prepare('0.4.0','win',d,'0.4.1',123,lambda *a,**k:None)
            self.assertEqual(list(d.iterdir()),[])

    def test_mac_identity_and_version_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)/'app';(d/'Contents').mkdir(parents=True)
            (d/'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier='other.app',CFBundleExecutable='X2DPlay',CFBundleShortVersionString='0.4.1')))
            with self.assertRaises(u.UpdateError):u.validate_app(d,'mac','0.4.1')

if __name__=='__main__':unittest.main()
