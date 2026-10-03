"""Windows 首次连接准备；固定相机 Interface 3，完成后仍需完整相机校验。"""
import hashlib, json, subprocess, time
from pathlib import Path
D=Path(__file__).resolve().parent

class DriverPreparationError(RuntimeError): pass

def driver_error(code):
    known={11:'未检测到相机工厂接口。请将相机开机、接入 USB 数据线，再点击“已连接”。',
        12:'检测到多台相机，请只连接一台后再点击“已连接”。',
        13:'驱动准备工具未通过参数检查，请重新解压完整安装包。',
        15:'需要 Windows 管理员权限，请双击安装包中的“耍起功能.exe”并允许系统授权。',
        16:'无法创建驱动准备目录，请检查 Windows 临时目录后重试。',
        103:'Windows 拒绝驱动安装，请检查系统权限后重试。',
        104:'准备驱动时相机已断开，请重新连接后重试。',
        106:'Windows 正在使用该接口，请关闭占用相机的程序后重试。',
        107:'Windows 驱动准备超时，请保持连接并稍后重试。',
        109:'Windows 仍在安装其他设备，请等待完成后重新点击“已连接”。',
        114:'已取消 Windows 驱动授权；相机功能尚未安装，可重新点击“已连接”。',
        115:'Windows 未授予驱动安装权限，请允许系统授权后重试。',
        117:'驱动安装配置未通过校验，请反馈此提示。',
        118:'驱动安装包签名目录未生成，请反馈此提示。',
        119:'Windows 未接受驱动安装包签名，请反馈此提示。'}
    return known.get(code,'Windows 驱动准备未完成（退出码 '+str(code)+'），请反馈此提示。')

def checked_helper(root):
    folder=root/'driver'; record=json.loads((folder/'provenance.json').read_text(encoding='utf-8'))
    for name in ('camera-driver.exe','libwdi.dll'):
        expected=record['files'][name]
        if len(expected)!=64 or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected:
            raise DriverPreparationError('驱动准备组件校验失败，请重新解压完整安装包。')
    return folder/'camera-driver.exe'

def helper_call(helper, action, emit, popen=subprocess.Popen, clock=time):
    # Fixed executable and fixed flags, no shell, user/device strings or INF paths.
    child=popen([str(helper),action],cwd=str(helper.parent),stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
    last=clock.monotonic()
    while child.poll() is None:
        if clock.monotonic()-last>=10:
            emit('progress',message='Windows 正在准备相机连接驱动，请保持连接并等待完成。',percent=0)
            last=clock.monotonic()
        clock.sleep(.2)
    # Never terminate an active system driver install on a UI timeout.
    return child.returncode

def prepare_driver(emit, root=D, call=helper_call, clock=time):
    helper=checked_helper(root)
    emit('progress',message='正在自动检查相机 USB 驱动；只需连接一台相机。',percent=0)
    code=call(helper,'--probe',emit)
    if code==0:
        emit('progress',message='相机 USB 驱动已就绪，正在核对相机固件与安装状态。',percent=0)
        return
    if code!=10: raise DriverPreparationError(driver_error(code))
    emit('progress',message='正在自动安装相机连接所需的 WinUSB 驱动；若 Windows 提示授权，请允许。',percent=0)
    code=call(helper,'--install',emit)
    if code: raise DriverPreparationError(driver_error(code))
    emit('progress',message='驱动准备完成，正在等待相机重新连接；请保持数据线连接。',percent=0)
    deadline=clock.monotonic()+30
    while clock.monotonic()<deadline:
        code=call(helper,'--probe',emit)
        if code==0:
            emit('progress',message='相机连接驱动已就绪，继续核对固件与安装状态。',percent=0)
            return
        if code not in (10,11): raise DriverPreparationError(driver_error(code))
        clock.sleep(1)
    raise DriverPreparationError('驱动已准备，但相机接口尚未恢复。请保持连接，稍后再点击“已连接”。')
