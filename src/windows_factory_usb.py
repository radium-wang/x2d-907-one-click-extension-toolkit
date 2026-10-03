"""Windows 工厂通信：仅打开已绑定 WinUSB 的 2756:0009 或 000A / MI_03。

复用原工厂帧协议；不经 libusb 打开复合设备的其他接口，不改驱动或设备权限。
"""
import ctypes as C
import re
import uuid
import collect_x2d_af_usb as usb

U8, U16, U32, BOOL, HANDLE = C.c_uint8, C.c_uint16, C.c_uint32, C.c_int32, C.c_void_p
INVALID = C.c_void_p(-1).value


class GUID(C.Structure):
    _fields_ = [('a', U32), ('b', U16), ('c', U16), ('d', U8 * 8)]


class DeviceInfo(C.Structure):
    _fields_ = [('cbSize', U32), ('ClassGuid', GUID), ('DevInst', U32), ('Reserved', C.c_size_t)]


class InterfaceInfo(C.Structure):
    _fields_ = [('cbSize', U32), ('ClassGuid', GUID), ('Flags', U32), ('Reserved', C.c_size_t)]


class UsbInterface(C.Structure):
    _pack_ = 1
    _fields_ = [(name, U8) for name in ('bLength', 'bDescriptorType', 'bInterfaceNumber',
        'bAlternateSetting', 'bNumEndpoints', 'bInterfaceClass', 'bInterfaceSubClass',
        'bInterfaceProtocol', 'iInterface')]


class PipeInfo(C.Structure):
    _fields_ = [('PipeType', U32), ('PipeId', U8), ('MaximumPacketSize', U16), ('Interval', U8)]


class WinUsbError(usb.UsbFactoryError):
    def __init__(self, step, code):
        self.winerror = code
        self.backend_error_code = {5:-3, 32:-6, 121:-7, 1460:-7, 1167:-4, 2:-4}.get(code, -1)
        reason = {5:'访问被拒绝', 32:'接口被占用', 121:'通信超时', 1460:'通信超时',
                  1167:'相机已断开', 2:'接口已断开'}.get(code, '操作未完成')
        super().__init__('Windows 工厂接口' + step + reason + '（系统错误码 ' + str(code) + '）')


def target_id(value):
    return bool(re.fullmatch(r'USB\\VID_2756&PID_(?:0009|000A)(?:&REV_[0-9A-F]{4})?&MI_03', value, re.I))


def target_path(value):
    parts = value.split('#')
    return len(parts) == 4 and parts[0].lower() == '\\\\?\\usb' and target_id('USB\\' + parts[1])


class WindowsAPI:
    def __init__(self):
        import winreg
        self.registry = winreg
        # System32-only loading: no search through the current folder for system DLLs.
        setup = C.WinDLL('setupapi.dll', use_last_error=True, winmode=0x800)
        kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        winusb = C.WinDLL('winusb.dll', use_last_error=True, winmode=0x800)
        def bind(dll, name, result, args):
            fn = getattr(dll, name); fn.restype = result; fn.argtypes = args
            setattr(self, name, fn)
        P, W = C.c_void_p, C.c_wchar_p
        bind(setup, 'SetupDiGetClassDevsW', HANDLE, [P,W,HANDLE,U32])
        bind(setup, 'SetupDiEnumDeviceInfo', BOOL, [HANDLE,U32,P])
        bind(setup, 'SetupDiGetDeviceRegistryPropertyW', BOOL, [HANDLE,P,U32,P,P,U32,P])
        bind(setup, 'SetupDiOpenDevRegKey', HANDLE, [HANDLE,P,U32,U32,U32,U32])
        bind(setup, 'SetupDiEnumDeviceInterfaces', BOOL, [HANDLE,P,P,U32,P])
        bind(setup, 'SetupDiGetDeviceInterfaceDetailW', BOOL, [HANDLE,P,P,U32,P,P])
        bind(setup, 'SetupDiDestroyDeviceInfoList', BOOL, [HANDLE])
        bind(kernel, 'CreateFileW', HANDLE, [W,U32,U32,P,U32,U32,HANDLE])
        bind(kernel, 'CloseHandle', BOOL, [HANDLE])
        bind(winusb, 'WinUsb_Initialize', BOOL, [HANDLE,P])
        bind(winusb, 'WinUsb_Free', BOOL, [HANDLE])
        bind(winusb, 'WinUsb_QueryInterfaceSettings', BOOL, [HANDLE,U8,P])
        bind(winusb, 'WinUsb_GetCurrentAlternateSetting', BOOL, [HANDLE,P])
        bind(winusb, 'WinUsb_QueryPipe', BOOL, [HANDLE,U8,U8,P])
        bind(winusb, 'WinUsb_SetPipePolicy', BOOL, [HANDLE,U8,U32,U32,P])
        bind(winusb, 'WinUsb_ReadPipe', BOOL, [HANDLE,U8,P,U32,P,P])
        bind(winusb, 'WinUsb_WritePipe', BOOL, [HANDLE,U8,P,U32,P,P])

    def check(self, result, step):
        if not result: raise WinUsbError(step, C.get_last_error())
        return result

    def property(self, devices, info, number):
        data = C.create_string_buffer(16384); kind, needed = U32(), U32()
        self.check(self.SetupDiGetDeviceRegistryPropertyW(devices, C.byref(info), number,
                   C.byref(kind), data, len(data), C.byref(needed)), '信息读取')
        if needed.value > len(data) or kind.value not in (1,7):
            raise usb.UsbFactoryError('Windows 工厂接口设备信息格式不符')
        return data.raw[:needed.value].decode('utf-16-le').rstrip('\0').split('\0')

    def interface_guids(self, devices, info):
        reg = self.registry
        key = self.SetupDiOpenDevRegKey(devices, C.byref(info), 1, 0, 1, reg.KEY_READ)
        if key == INVALID: raise WinUsbError('驱动信息读取', C.get_last_error())
        try:
            # DIREG_DEV already returns the hardware parameters key. Query it
            # directly, as libusb's get_guid does; do not descend a second time.
            try: values, kind = reg.QueryValueEx(key, 'DeviceInterfaceGUIDs')
            except FileNotFoundError: values, kind = reg.QueryValueEx(key, 'DeviceInterfaceGUID')
            if kind == reg.REG_SZ: values = [values]
            elif kind != reg.REG_MULTI_SZ: raise ValueError()
            if not values or len(values) > 16: raise ValueError()
            return [GUID.from_buffer_copy(uuid.UUID(value).bytes_le) for value in values]
        except OSError as error:
            code = getattr(error,'winerror',None) or error.errno or 0
            reason = {2:'未找到接口标识',5:'读取被拒绝'}.get(code,'读取未完成')
            raise usb.UsbFactoryError('Windows 工厂接口标识' + reason + '（系统错误码 ' + str(code) + '），请反馈此提示') from None
        except (ValueError, TypeError, AttributeError):
            raise usb.UsbFactoryError('Windows 工厂接口标识格式未通过校验，请反馈此提示') from None
        finally: reg.CloseKey(key)

    def factory_path(self):
        devices = self.SetupDiGetClassDevsW(None, 'USB', None, 2|4)  # present + all classes
        if devices == INVALID: raise WinUsbError('枚举', C.get_last_error())
        try:
            matches = []
            for index in range(4096):
                info = DeviceInfo(); info.cbSize = C.sizeof(info)
                if not self.SetupDiEnumDeviceInfo(devices, index, C.byref(info)):
                    if C.get_last_error() != 259: raise WinUsbError('枚举', C.get_last_error())
                    break
                # Hardware IDs identify the interface; friendly names are not trusted.
                try: ids = self.property(devices, info, 1)
                except WinUsbError as error:
                    if error.winerror == 13: continue  # An unrelated node without hardware IDs.
                    raise
                if any(target_id(value) for value in ids):
                    matches.append(info)
            else: raise usb.UsbFactoryError('Windows 工厂接口枚举数量异常')
            if not matches: raise usb.UsbFactoryError('USB camera was not enumerated')
            if len(matches) != 1: raise usb.UsbFactoryError('Windows 工厂接口检测到多台相机，请只连接一台')
            info = matches[0]
            if [value.lower() for value in self.property(devices, info, 4)] != ['winusb']:
                raise usb.UsbFactoryError('Windows 工厂接口 Interface 3 未绑定 WinUSB，请检查对应接口驱动')
            paths = set()
            for guid in self.interface_guids(devices, info):
                interfaces = self.SetupDiGetClassDevsW(C.byref(guid),None,None,2|16)
                if interfaces == INVALID: raise WinUsbError('接口枚举',C.get_last_error())
                try:
                    paths.update(self.paths_for_guid(interfaces,guid,info.DevInst))
                finally: self.SetupDiDestroyDeviceInfoList(interfaces)
            if not paths: raise usb.UsbFactoryError('Windows 工厂接口路径未识别，请反馈此提示')
            # Multiple registered GUID aliases may refer to the same verified MI_03.
            return sorted(paths)[0]
        finally: self.SetupDiDestroyDeviceInfoList(devices)

    def paths_for_guid(self, devices, guid, devinst):
        paths = []
        for index in range(128):
            iface = InterfaceInfo(); iface.cbSize = C.sizeof(iface)
            if not self.SetupDiEnumDeviceInterfaces(devices,None,C.byref(guid),index,C.byref(iface)):
                if C.get_last_error() != 259: raise WinUsbError('接口枚举',C.get_last_error())
                break
            needed = U32(); related = DeviceInfo(); related.cbSize = C.sizeof(related)
            ok = self.SetupDiGetDeviceInterfaceDetailW(devices,C.byref(iface),None,0,C.byref(needed),None)
            if ok or C.get_last_error() != 122 or not 6 <= needed.value <= 16384:
                raise usb.UsbFactoryError('Windows 工厂接口路径长度未通过校验')
            data = C.create_string_buffer(needed.value)
            # Windows x64: fixed struct size 8, DevicePath begins at offset 4.
            U32.from_buffer(data).value = 8 if C.sizeof(HANDLE) == 8 else 6
            self.check(self.SetupDiGetDeviceInterfaceDetailW(devices,C.byref(iface),data,len(data),
                       C.byref(needed),C.byref(related)), '接口路径读取')
            if related.DevInst != devinst: continue
            path = data.raw[4:needed.value].decode('utf-16-le').split('\0',1)[0]
            if not target_path(path):
                raise usb.UsbFactoryError('Windows 工厂接口路径与 Interface 3 不匹配')
            paths.append(path)
        else: raise usb.UsbFactoryError('Windows 工厂接口路径数量异常')
        return paths


class Endpoint:
    def __init__(self, reader, address): self.reader, self.address = reader, address

    def transfer(self, buffer, size, timeout, write):
        owner = self.reader; api = owner.api
        duration, done = U32(max(1,timeout)), U32()
        api.check(api.WinUsb_SetPipePolicy(owner.handle,self.address,3,C.sizeof(duration),C.byref(duration)), '超时设置')
        function = api.WinUsb_WritePipe if write else api.WinUsb_ReadPipe
        api.check(function(owner.handle,self.address,buffer,size,C.byref(done),None), '发送' if write else '接收')
        if done.value > size: raise usb.UsbFactoryError('Windows 工厂接口传输长度异常')
        return done.value

    def write(self, data, timeout):
        buffer = C.create_string_buffer(bytes(data),len(data))
        return self.transfer(buffer,len(data),timeout,True)

    def read(self, size, timeout):
        buffer = C.create_string_buffer(size)
        count = self.transfer(buffer,size,timeout,False)
        return buffer.raw[:count]


class WindowsFactoryReader(usb.FactoryUsbReader):
    def __init__(self, timeout_ms=15000, api=None):
        self.timeout_ms = timeout_ms
        self.api = api
        self.file = None; self.handle = HANDLE()
        self.device = None; self.out_ep = None; self.in_ep = None
        self.last_factory_transport_bytes = 0; self.last_factory_discarded_bytes = 0; self.last_factory_preview = b''

    def __enter__(self):
        try:
            if self.api is None: self.api = WindowsAPI()
            api = self.api; path = api.factory_path()
            if not target_path(path): raise usb.UsbFactoryError('Windows 工厂接口路径未通过校验')
            # Only MI_03; never open associated ADB, storage or network interfaces.
            self.file = api.CreateFileW(path,0xc0000000,3,None,3,0x40000000,None)
            if self.file == INVALID: raise WinUsbError('打开',C.get_last_error())
            api.check(api.WinUsb_Initialize(self.file,C.byref(self.handle)), '初始化')
            descriptor, current = UsbInterface(), U8()
            api.check(api.WinUsb_QueryInterfaceSettings(self.handle,0,C.byref(descriptor)), '描述符读取')
            api.check(api.WinUsb_GetCurrentAlternateSetting(self.handle,C.byref(current)), '配置读取')
            if (descriptor.bLength,descriptor.bDescriptorType,descriptor.bInterfaceNumber,
                descriptor.bAlternateSetting,current.value) != (9,4,3,0,0):
                raise usb.UsbFactoryError('Windows 工厂接口 Interface 3 描述符未通过校验')
            endpoints = {}
            for index in range(descriptor.bNumEndpoints):
                pipe = PipeInfo()
                api.check(api.WinUsb_QueryPipe(self.handle,0,index,C.byref(pipe)), '端点读取')
                if pipe.PipeType == 2: endpoints[pipe.PipeId] = pipe.MaximumPacketSize
            if not endpoints.get(0x04) or not endpoints.get(0x85):
                raise usb.UsbFactoryError('Windows 工厂接口 OUT 04 / IN 85 端点未通过校验')
            self.out_ep, self.in_ep = Endpoint(self,0x04), Endpoint(self,0x85)
            return self
        except Exception:
            self.close()
            raise

    def close(self):
        self.out_ep = None; self.in_ep = None
        if self.handle.value:
            self.api.WinUsb_Free(self.handle); self.handle = HANDLE()
        if self.file is not None and self.file != INVALID:
            self.api.CloseHandle(self.file)
        self.file = None

    @staticmethod
    def _is_timeout(error):
        return getattr(error,'winerror',None) in (121,1460) or usb.FactoryUsbReader._is_timeout(error)
