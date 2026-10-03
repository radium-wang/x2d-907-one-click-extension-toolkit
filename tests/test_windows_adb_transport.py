"""无设备检查：WinUSB 仅打开 MI_03，与被 ADB 占用的其他接口共存。"""
import ctypes as C
import struct
import unittest
from unittest.mock import MagicMock, patch
import x2d_play_software as app
import windows_factory_usb as native
from test_adb_reconnect import Clock

PATH = r'\\?\usb#vid_2756&pid_0009&mi_03#synthetic-device#{01234567-89ab-cdef-0123-456789abcdef}'

def setvalue(pointer, kind, value): C.cast(pointer,C.POINTER(kind)).contents.value=value

class NativeAPI:
    def __init__(self):
        self.opened=[];self.freed=[];self.closed=[];self.policies=[];self.writes=[];self.queue=[]
        self.interface=3;self.endpoints=[4,0x85];self.fail_at=None;self.return_handle=10
        self.error=0;self.values={'getprop ro.product.device':'eagle2_ec1706_native',
            'sha256sum /system/bin/camera-gui':app.STOCK_GUI+' /system/bin/camera-gui'}
    def check(self,result,step):
        if not result: raise native.WinUsbError(step,self.error or 5)
        return result
    def factory_path(self): return PATH
    def CreateFileW(self,path,*options):
        self.opened.append(path)
        # Another WinUSB interface is held by ADB; opening it would be refused.
        if 'mi_03' not in path: raise AssertionError('opened ADB interface')
        return self.return_handle
    def WinUsb_Initialize(self,file,output):
        if self.fail_at=='initialize': return False
        setvalue(output,native.HANDLE,20);return True
    def WinUsb_QueryInterfaceSettings(self,handle,alt,output):
        descriptor=C.cast(output,C.POINTER(native.UsbInterface)).contents
        descriptor.bLength=9;descriptor.bDescriptorType=4;descriptor.bInterfaceNumber=self.interface
        descriptor.bNumEndpoints=len(self.endpoints);return True
    def WinUsb_GetCurrentAlternateSetting(self,handle,output): setvalue(output,native.U8,0);return True
    def WinUsb_QueryPipe(self,handle,alt,index,output):
        descriptor=C.cast(output,C.POINTER(native.PipeInfo)).contents
        descriptor.PipeType=2;descriptor.PipeId=self.endpoints[index];descriptor.MaximumPacketSize=512
        return True
    def WinUsb_Free(self,handle): self.freed.append(handle.value);return True
    def CloseHandle(self,file): self.closed.append(file);return True
    def WinUsb_SetPipePolicy(self,handle,address,policy,size,value):
        self.policies.append((address,policy,C.cast(value,C.POINTER(native.U32)).contents.value));return True
    def WinUsb_WritePipe(self,handle,address,buffer,size,done,overlapped):
        request=buffer.raw[:size];self.writes.append((address,request))
        command=request[25:].split(b'\0',1)[0].decode('ascii')
        cookie=struct.unpack_from('<I',request,13)[0]
        for function,text in [(4,self.values[command]),(0,'')]:
            payload=bytearray(252);struct.pack_into('<III',payload,0,65,function,cookie)
            encoded=text.encode();payload[20:20+len(encoded)]=encoded
            struct.pack_into('<I',payload,12,app.usb.crc16_xmodem(payload[16:]))
            self.queue.append(app.usb.FACTORY_RESPONSE_HEADER+payload)
        setvalue(done,native.U32,size);return True
    def WinUsb_ReadPipe(self,handle,address,buffer,size,done,overlapped):
        if not self.queue: self.error=121;return False
        data=self.queue.pop(0);C.memmove(buffer,data,len(data));setvalue(done,native.U32,len(data));return True

class EnumerateAPI(native.WindowsAPI):
    def __init__(self):
        self.error=0;self.destroyed=[];self.flags=[];self.ids=['USB\\VID_1234&PID_5678&MI_03','USB\\VID_2756&PID_0009&MI_03']
        self.driver='WinUSB';self.interface_paths=[(99,PATH.replace('mi_03','mi_05')),(2,PATH)]
        self.opened=[]
    def SetupDiGetClassDevsW(self,guid,enumerator,window,flags): self.flags.append(flags);return 200 if guid else 100
    def SetupDiEnumDeviceInfo(self,devices,index,output):
        if index>=len(self.ids): self.error=259;return False
        C.cast(output,C.POINTER(native.DeviceInfo)).contents.DevInst=index+1;return True
    def property(self,devices,info,number): return [self.ids[info.DevInst-1]] if number==1 else [self.driver]
    def interface_guids(self,*args): return [native.GUID()]
    def SetupDiEnumDeviceInterfaces(self,devices,info,guid,index,output):
        assert info is None and devices==200
        if index>=len(self.interface_paths): self.error=259;return False
        C.cast(output,C.POINTER(native.InterfaceInfo)).contents.Reserved=index;return True
    def SetupDiGetDeviceInterfaceDetailW(self,devices,iface,output,size,needed,info):
        index=C.cast(iface,C.POINTER(native.InterfaceInfo)).contents.Reserved
        devinst,path=self.interface_paths[index];encoded=(path+'\0').encode('utf-16-le')
        setvalue(needed,native.U32,4+len(encoded))
        if output is None: self.error=122;return False
        assert native.U32.from_buffer(output).value==8
        C.memmove(C.addressof(output)+4,encoded,len(encoded))
        C.cast(info,C.POINTER(native.DeviceInfo)).contents.DevInst=devinst;return True
    def SetupDiDestroyDeviceInfoList(self,devices): self.destroyed.append(devices);return True

class WindowsFactoryTests(unittest.TestCase):
    def test_guid_registry_lookup_is_readonly_and_closes_key(self):
        api=EnumerateAPI();registry=MagicMock()
        registry.KEY_READ=0x20019;registry.REG_SZ=1;registry.REG_MULTI_SZ=7
        # SetupDiOpenDevRegKey already supplies the hardware parameters key.
        # An additional child does not exist on the reported Windows installation.
        registry.OpenKey.side_effect=FileNotFoundError(2,'private-registry-path')
        registry.QueryValueEx.return_value=('{01234567-89ab-cdef-0123-456789abcdef}',1)
        api.registry=registry;api.SetupDiOpenDevRegKey=MagicMock(return_value=44)
        info=native.DeviceInfo()
        values=native.WindowsAPI.interface_guids(api,100,info)
        self.assertEqual(len(values),1)
        self.assertEqual(C.string_at(C.byref(values[0]),16).hex(),'67452301ab89efcd0123456789abcdef')
        self.assertEqual(api.SetupDiOpenDevRegKey.call_args.args[-1],registry.KEY_READ)
        registry.OpenKey.assert_not_called()
        registry.QueryValueEx.assert_called_once_with(44,'DeviceInterfaceGUIDs')
        registry.CloseKey.assert_called_once_with(44)

    def test_invalid_registry_guid_is_rejected_and_key_is_closed(self):
        api=EnumerateAPI();registry=MagicMock()
        registry.KEY_READ=0x20019;registry.REG_SZ=1;registry.REG_MULTI_SZ=7
        registry.QueryValueEx.return_value=('not-a-guid',1)
        api.registry=registry;api.SetupDiOpenDevRegKey=MagicMock(return_value=44)
        with self.assertRaisesRegex(app.usb.UsbFactoryError,'接口标识'):
            native.WindowsAPI.interface_guids(api,100,native.DeviceInfo())
        registry.CloseKey.assert_called_once_with(44)

    def registry_api(self):
        api=EnumerateAPI();registry=MagicMock()
        registry.KEY_READ=0x20019;registry.REG_SZ=1;registry.REG_MULTI_SZ=7
        registry.OpenKey.side_effect=AssertionError('must query supplied hardware key directly')
        api.registry=registry;api.SetupDiOpenDevRegKey=MagicMock(return_value=44)
        return api,registry

    def test_multiple_guid_value_is_read_from_supplied_key(self):
        api,registry=self.registry_api()
        registry.QueryValueEx.return_value=(['{01234567-89ab-cdef-0123-456789abcdef}',
                                            '{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}'],7)
        values=native.WindowsAPI.interface_guids(api,100,native.DeviceInfo())
        self.assertEqual(len(values),2);registry.OpenKey.assert_not_called()
        registry.CloseKey.assert_called_once_with(44)

    def test_legacy_singular_guid_name_is_supported(self):
        api,registry=self.registry_api()
        registry.QueryValueEx.side_effect=[FileNotFoundError(2,'private-path'),('{01234567-89ab-cdef-0123-456789abcdef}',1)]
        self.assertEqual(len(native.WindowsAPI.interface_guids(api,100,native.DeviceInfo())),1)
        self.assertEqual([call.args for call in registry.QueryValueEx.call_args_list],
                         [(44,'DeviceInterfaceGUIDs'),(44,'DeviceInterfaceGUID')])
        registry.CloseKey.assert_called_once_with(44)

    def test_missing_and_denied_registry_values_have_distinct_private_safe_diagnostics(self):
        for code,reason in [(2,'未找到'),(5,'读取被拒绝')]:
            api,registry=self.registry_api();error=OSError(code,'private-path-identity')
            error.winerror=code;registry.QueryValueEx.side_effect=error
            with self.assertRaises(app.usb.UsbFactoryError) as failure:
                native.WindowsAPI.interface_guids(api,100,native.DeviceInfo())
            self.assertIn(reason,str(failure.exception));self.assertIn('系统错误码 '+str(code),str(failure.exception))
            self.assertNotIn('private',app.user_error(failure.exception))
            registry.CloseKey.assert_called_once_with(44)

    def test_empty_or_wrong_registry_types_never_reach_interface_open(self):
        for value,kind in [([],7),('bad-type',3),(['not-a-guid'],7),([None],7)]:
            api,registry=self.registry_api();registry.QueryValueEx.return_value=(value,kind)
            with self.assertRaisesRegex(app.usb.UsbFactoryError,'格式未通过'):
                native.WindowsAPI.interface_guids(api,100,native.DeviceInfo())
            registry.CloseKey.assert_called_once_with(44)

    def test_windows_x64_abi_uses_fixed_windows_field_sizes(self):
        self.assertEqual([C.sizeof(kind) for kind in (native.GUID,native.DeviceInfo,native.InterfaceInfo,native.UsbInterface,native.PipeInfo)], [16,32,32,9,12])
        self.assertEqual(native.DeviceInfo.Reserved.offset,24)
    def test_ids_and_paths_reject_composite_adb_and_other_devices(self):
        self.assertTrue(native.target_id('USB\\VID_2756&PID_0009&REV_0400&MI_03'))
        self.assertTrue(native.target_path(PATH))
        for bad in ['USB\\VID_2756&PID_0009','USB\\VID_2756&PID_0009&MI_05','USB\\VID_2756&PID_0009&MI_030']:
            self.assertFalse(native.target_id(bad))
        self.assertFalse(native.target_path(PATH.replace('mi_03','mi_05')))
    def test_enumeration_filters_present_hardware_and_related_devinst(self):
        api=EnumerateAPI()
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            self.assertEqual(api.factory_path(),PATH)
        self.assertEqual(api.flags,[6,18]);self.assertEqual(api.destroyed,[200,100])
    def test_multiple_camera_nodes_are_rejected_before_interface_open(self):
        api=EnumerateAPI();api.ids.append(api.ids[1])
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            with self.assertRaisesRegex(app.usb.UsbFactoryError,'多台'): api.factory_path()
        self.assertEqual(api.flags,[6]);self.assertEqual(api.destroyed,[100])
    def test_wrong_driver_is_reported_without_opening_device(self):
        api=EnumerateAPI();api.driver='usbccgp'
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            with self.assertRaisesRegex(app.usb.UsbFactoryError,'未绑定 WinUSB'): api.factory_path()
        self.assertEqual(api.flags,[6]);self.assertEqual(api.destroyed,[100])
    def test_matching_devinst_with_wrong_interface_path_is_rejected(self):
        api=EnumerateAPI();api.interface_paths=[(2,PATH.replace('mi_03','mi_05'))]
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            with self.assertRaisesRegex(app.usb.UsbFactoryError,'不匹配'): api.factory_path()
        self.assertEqual(api.destroyed,[200,100])
    def test_only_factory_handle_is_opened_and_closed_even_when_adb_is_busy(self):
        api=NativeAPI();reader=native.WindowsFactoryReader(api=api)
        with reader: self.assertIsNotNone(reader.in_ep)
        reader.close()
        self.assertEqual(api.opened,[PATH]);self.assertEqual(api.freed,[20]);self.assertEqual(api.closed,[10])
    def test_initialization_failure_closes_file_and_does_not_free_invalid_handle(self):
        api=NativeAPI();api.fail_at='initialize'
        with self.assertRaises(native.WinUsbError): native.WindowsFactoryReader(api=api).__enter__()
        self.assertEqual(api.closed,[10]);self.assertEqual(api.freed,[])
    def test_descriptor_and_endpoint_failures_close_both_handles(self):
        for field,value in [('interface',5),('endpoints',[4,0x86])]:
            api=NativeAPI();setattr(api,field,value)
            with self.assertRaises(app.usb.UsbFactoryError): native.WindowsFactoryReader(api=api).__enter__()
            self.assertEqual(api.closed,[10]);self.assertEqual(api.freed,[20])
    def test_protocol_crc_cookie_notifications_and_exact_target_hash_still_pass(self):
        api=NativeAPI();clock=Clock()
        with patch.object(app.usb.time,'monotonic',side_effect=lambda:(setattr(clock,'now',clock.now+0.01) or clock.now)):
            with native.WindowsFactoryReader(api=api) as reader: app.usb.validate_factory_gui_target(reader)
        self.assertEqual(len(api.writes),2)
        self.assertTrue(all(address==4 for address,_ in api.writes))
        self.assertTrue(all(policy==3 and timeout>0 for _,policy,timeout in api.policies))
    def test_changed_gui_is_rejected_by_original_validator(self):
        api=NativeAPI();api.values['sha256sum /system/bin/camera-gui']='0'*64+' file'
        clock=Clock()
        with patch.object(app.usb.time,'monotonic',side_effect=lambda:(setattr(clock,'now',clock.now+0.01) or clock.now)):
            with native.WindowsFactoryReader(api=api) as reader:
                with self.assertRaisesRegex(app.usb.UsbFactoryError,'unknown'): app.usb.validate_factory_gui_target(reader)
    def test_native_error_uses_chinese_numeric_diagnostics_without_private_path(self):
        for code in (5,32,121,1167):
            error=native.WinUsbError('打开',code)
            self.assertIn('系统错误码 '+str(code),app.user_error(error))
            self.assertTrue(native.WindowsFactoryReader._is_timeout(error)==(code==121))
    def test_windows_routes_all_shell_commands_to_factory_and_not_adb_shell(self):
        api=NativeAPI();clock=Clock()
        with patch.object(app.os,'name','nt'),patch.object(native,'WindowsAPI',return_value=api), \
             patch.object(app,'adb_call') as adb, \
             patch.object(app.usb.time,'monotonic',side_effect=lambda:(setattr(clock,'now',clock.now+0.01) or clock.now)):
            self.assertEqual(app.shell('getprop ro.product.device'),'eagle2_ec1706_native')
            adb.assert_not_called()
        self.assertEqual(api.opened,[PATH])
    def test_upload_still_uses_pinned_adb_then_factory_hash_and_syntax(self):
        data=b'#!/system/bin/sh\nset -eu\necho SAFE\n'
        with patch.object(app,'ADB_SERIAL','synthetic-device'),patch.object(app,'shell',side_effect=['SAFE',app.sha(data)+' file','SYNTAX_OK']) as shell, \
             patch.object(app.subprocess,'run',return_value=MagicMock(returncode=0)) as run:
            app.upload('restore',data)
        self.assertEqual(run.call_args.args[0][1:4],['-s','synthetic-device','push'])
        self.assertIn('sha256sum',shell.call_args_list[1].args[0]);self.assertIn('sh -n',shell.call_args_list[2].args[0])

if __name__=='__main__': unittest.main()
