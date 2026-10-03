"""GitHub release updates. Never imports or operates the camera transport."""
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = 'radium-wang/x2d-907-one-click-extension-toolkit'
API = 'https://api.github.com/repos/' + REPO + '/releases/latest'
BASE = 'x2d-907一键扩展功能-工具包'
MAX_DOWNLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024


class UpdateError(Exception):
    pass


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise UpdateError('更新版本信息无效')
    return tuple(map(int, value.lstrip('v').split('.')))


def context():
    # The portable macOS Python has no installer-created certifi symlink.
    # Use Apple system roots; never disable HTTPS verification.
    if sys.platform == 'darwin':
        roots = subprocess.run(['/usr/bin/security', 'find-certificate', '-a', '-p',
                                '/System/Library/Keychains/SystemRootCertificates.keychain'],
                               check=True, capture_output=True, timeout=15).stdout.decode('ascii')
        return ssl.create_default_context(cadata=roots)
    return ssl.create_default_context()


def request(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'X2D-907-Extension-Toolkit',
                                 'Accept': 'application/vnd.github+json'})
    return urllib.request.urlopen(req, context=context(), timeout=30)


def latest(current, platform, opener=request):
    version(current)
    try:
        with opener(API) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024: raise UpdateError('更新信息过大，已停止检查')
            release = json.loads(raw)
    except urllib.error.HTTPError as error:
        if error.code == 404: return None
        if error.code in (403, 429): raise UpdateError('检查更新暂时受限，请稍后重试') from error
        raise
    if release.get('draft') or release.get('prerelease'):
        raise UpdateError('更新信息无效，未使用预发布版本')
    tag = release.get('tag_name')
    if version(tag) <= version(current): return None
    new = tag.lstrip('v')
    suffix = {'mac': 'macOS-Universal', 'win': 'Windows-x64'}[platform]
    name = BASE + '-' + suffix + '-' + new + '.zip'
    matches = [a for a in release.get('assets', []) if a.get('name') == name]
    if len(matches) != 1: raise UpdateError('新版暂未提供本系统安装包，请稍后重试')
    asset = matches[0]
    digest = asset.get('digest', '')
    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise UpdateError('更新包缺少有效校验信息，已停止更新')
    expected = 'https://github.com/' + REPO + '/releases/download/' + tag + '/' + name
    if urllib.parse.unquote(asset.get('browser_download_url', '')) != expected:
        raise UpdateError('更新下载地址不属于本项目，已停止更新')
    size = asset.get('size')
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_DOWNLOAD:
        raise UpdateError('更新包大小无效，已停止更新')
    return dict(version=new, url=urllib.parse.quote(expected, safe=':/'), size=size,
                sha256=digest.split(':')[1], name=name, platform=platform)


def download(info, destination, emit, opener=request):
    total = 0
    digest = hashlib.sha256()
    last = -1
    try:
        with opener(info['url']) as response, destination.open('xb') as output:
            while True:
                block = response.read(1024 * 1024)
                if not block: break
                total += len(block)
                if total > info['size']: raise UpdateError('下载大小与发布信息不符，已停止更新')
                output.write(block); digest.update(block)
                percent = total * 100 // info['size']
                if percent // 10 != last:
                    last = percent // 10
                    emit('progress', '正在下载软件更新，请保持网络连接', percent=percent)
        if total != info['size'] or digest.hexdigest() != info['sha256']:
            raise UpdateError('更新包校验失败，当前版本未被替换')
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def extract(archive, directory, platform):
    root = BASE + ('.app' if platform == 'mac' else '-Windows-x64')
    seen = set()
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist()) > MAX_EXPANDED or len(z.infolist()) > 20000:
            raise UpdateError('更新包解压大小异常，已停止更新')
        for entry in z.infolist():
            parts = PurePosixPath(entry.filename).parts
            mode = entry.external_attr >> 16
            if (not parts or entry.filename.startswith('/') or '\\' in entry.filename
                    or any(p in ('.', '..') or ':' in p for p in parts)
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise UpdateError('更新包包含不安全路径，已停止更新')
            key = entry.filename.rstrip('/').casefold()
            if key in seen: raise UpdateError('更新包包含重复路径，已停止更新')
            seen.add(key)
            if parts[0] != root:
                if platform == 'mac' and parts == ('使用说明-macOS.txt',): continue
                raise UpdateError('更新包目录不符合本应用结构，已停止更新')
            target = directory.joinpath(*parts)
            if entry.is_dir(): target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if mode & 0o111 else 0o644)
    return directory / root


def validate_app(path, platform, expected=None):
    if path.is_symlink() or not path.is_dir(): raise UpdateError('应用目录无效，已停止更新')
    if platform == 'mac':
        info = plistlib.loads((path / 'Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier') != 'local.x2d.play' or info.get('CFBundleExecutable') != 'X2DPlay':
            raise UpdateError('更新包应用标识不匹配，已停止更新')
        found = info.get('CFBundleShortVersionString')
        required = ['Contents/MacOS/X2DPlay', 'Contents/Resources/runtime/bin/python3.13',
                    'Contents/Resources/app_updates.py', 'Contents/Resources/native-package/speed-bundle.json']
    else:
        found = json.loads((path / '版本与校验.json').read_text(encoding='utf-8'))['version']
        required = [BASE + '.exe', 'runtime/pythonw.exe', 'windows_app.py', 'app_updates.py',
                    'native-package/speed-bundle.json']
    version(found)
    if expected and found != expected: raise UpdateError('安装包版本与发布信息不符，已停止更新')
    if any(not (path / p).is_file() for p in required):
        raise UpdateError('更新包文件不完整，已停止更新')
    if platform == 'mac':
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(path)],
                       check=True, capture_output=True, timeout=60)
    return found


def swap(staged, target, backup, platform, expected):
    """Rollback if the second rename fails. The target is only a verified toolkit."""
    validate_app(staged, platform, expected)
    validate_app(target, platform)
    if backup.exists(): raise UpdateError('上一版备份已存在，已停止替换')
    # Antivirus or the just-exiting worker may briefly retain Windows handles.
    for attempt in range(60 if platform == 'win' and os.name == 'nt' else 1):
        try:
            target.rename(backup)
            break
        except PermissionError:
            if attempt == 59 or os.name != 'nt' or platform != 'win': raise
            time.sleep(0.5)
    try:
        staged.rename(target)
    except Exception:
        backup.rename(target)
        raise


def schedule(staged, target, folder, platform, expected, parent):
    validate_app(target, platform)
    # Stage beside the installed app, so replacement stays on the same volume.
    if folder.parent != target.parent or staged.parent != folder / 'stage':
        raise UpdateError('更新暂存目录无效，已停止更新')
    helper = folder / 'helper'; helper.mkdir()
    source = Path(__file__).resolve()
    shutil.copy2(source, helper / 'app_updates.py')
    resources = target / 'Contents/Resources' if platform == 'mac' else target
    shutil.copytree(resources / 'runtime', helper / 'runtime')
    if platform == 'mac':
        # Preserve the relative layout of relocated libraries.
        shutil.copytree(resources / 'lib', helper / 'lib')
        python = helper / 'runtime/bin/python3.13'
    else:
        python = helper / 'runtime/pythonw.exe'
    plan = dict(target=str(target), staged=str(staged), platform=platform, version=expected,
                parent=parent, backup=str(folder / ('previous.app' if platform == 'mac' else 'previous')))
    planfile = folder / 'plan.json'
    planfile.write_text(json.dumps(plan), encoding='utf-8')
    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME', 'X2D_PAYLOAD_DIR'): env.pop(name, None)
    env.update(PYTHONNOUSERSITE='1', PYTHONUTF8='1')
    if platform == 'mac': env['PYTHONHOME'] = str(helper / 'runtime')
    options = {'creationflags': 0x08000008} if platform == 'win' else {'start_new_session': True}
    subprocess.Popen([str(python), '-B', str(helper / 'app_updates.py'), 'apply', '--plan', str(planfile)],
                     cwd=str(helper), env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)


def wait_parent(pid):
    if os.name == 'nt':
        import ctypes as c
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [c.c_ulong, c.c_int, c.c_ulong]
        kernel.OpenProcess.restype = c.c_void_p
        kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_ulong]
        kernel.WaitForSingleObject.restype = c.c_ulong
        kernel.CloseHandle.argtypes = [c.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 120000) != 0:
                    raise UpdateError('应用尚未退出，更新未替换当前版本')
            finally: kernel.CloseHandle(handle)
    else:
        end = time.monotonic() + 120
        while time.monotonic() < end:
            try: os.kill(pid, 0)
            except ProcessLookupError: return
            time.sleep(0.25)
        raise UpdateError('应用尚未退出，更新未替换当前版本')


def apply(planfile):
    folder = planfile.resolve().parent
    plan = json.loads(planfile.read_text(encoding='utf-8'))
    target, staged, backup = map(Path, (plan['target'], plan['staged'], plan['backup']))
    if (not folder.name.startswith('.toolkit-update-') or folder.parent != target.parent
            or staged.parent != folder / 'stage' or backup.parent != folder):
        raise UpdateError('更新暂存目录无效，已停止更新')
    wait_parent(plan['parent'])
    def launch():
        if plan['platform'] == 'mac':
            subprocess.run(['/usr/bin/open', str(target)], check=True, timeout=30)
        else:
            subprocess.Popen([str(target / (BASE + '.exe'))], cwd=str(target))
    try:
        swap(staged, target, backup, plan['platform'], plan['version'])
        (folder / 'result.json').write_text(json.dumps(dict(success=True, version=plan['version'])), encoding='utf-8')
        launch()
    except Exception as error:
        # A failed launch restores the previous installation too.
        if backup.exists() and target.exists():
            target.rename(folder / 'failed-new-version')
            backup.rename(target)
        (folder / 'result.json').write_text(json.dumps(dict(success=False, error=str(error))), encoding='utf-8')
        if target.exists():
            try: launch()
            except Exception: pass
        raise


def notice(target):
    """Consume a local result once, only for this exact installation path."""
    for folder in sorted(target.parent.glob('.toolkit-update-*'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            if (folder / 'notified').exists(): continue
            plan = json.loads((folder / 'plan.json').read_text(encoding='utf-8'))
            if plan['target'] != str(target.resolve()): continue
            result = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
            (folder / 'notified').touch()
            return '软件更新安装完成，上一版已保留在应用旁的更新备份目录' if result['success'] else '软件更新未能安装，已保留或恢复上一版；请关闭占用软件的程序后重试'
        except (OSError, ValueError, KeyError): continue
    return ''


def prepare(current, platform, target, wanted, parent, emit):
    info = latest(current, platform)
    if not info or info['version'] != wanted:
        raise UpdateError('发布版本已变化，请重新点击“检查更新”')
    validate_app(target, platform, current)
    # A permission failure leaves the installed app intact and offers a clear next step.
    try: folder = Path(tempfile.mkdtemp(prefix='.toolkit-update-', dir=str(target.parent)))
    except OSError as error:
        raise UpdateError('应用所在目录无法写入，请将完整应用移到可写目录后重试') from error
    folder.chmod(0o700)
    try:
        archive = folder / 'download.zip'
        download(info, archive, emit)
        emit('progress', '下载完成，正在校验并准备安装', percent=100)
        staged = extract(archive, folder / 'stage', platform)
        validate_app(staged, platform, wanted)
        schedule(staged, target, folder, platform, wanted, parent)
        archive.unlink()
    except Exception:
        shutil.rmtree(folder)
        raise
    emit('restart', '更新已就绪，应用将退出、安装新版并重新打开', version=wanted)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['check', 'install', 'apply'])
    p.add_argument('--current'); p.add_argument('--platform', choices=['mac', 'win'])
    p.add_argument('--target', type=Path); p.add_argument('--wanted')
    p.add_argument('--parent', type=int); p.add_argument('--plan', type=Path)
    a = p.parse_args()
    def emit(kind, message, **values):
        print('TOOLKIT_UPDATE ' + json.dumps(dict(type=kind, message=message, **values), ensure_ascii=False), flush=True)
    try:
        if a.action == 'apply': apply(a.plan); return
        if a.action == 'check':
            emit('progress', '正在从 GitHub 检查软件更新', percent=0)
            info = latest(a.current, a.platform)
            emit('available' if info else 'current', '发现软件新版本，点击“下载并安装更新”即可更新'
                 if info else '当前已是最新可用版本', version=info['version'] if info else a.current)
        else: prepare(a.current, a.platform, a.target.resolve(), a.wanted, a.parent, emit)
    except Exception as error:
        emit('error', str(error) if isinstance(error, UpdateError)
             else '软件更新未完成，请检查网络连接或重新下载完整安装包；当前应用仍保留')
        sys.exit(1)


if __name__ == '__main__': main()
