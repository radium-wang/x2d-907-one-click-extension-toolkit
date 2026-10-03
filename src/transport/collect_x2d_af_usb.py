#!/usr/bin/env python3
"""Read and narrowly exercise the X2D factory USB interfaces.

This is deliberately separate from the Wi-Fi/ADB collector.  The factory USB
interface is not Android ADB: on the documented X2D 100C 4.2.0 unit it is
VID:PID 2756:0009, interface 3 alternate setting 0, with control bulk
endpoints OUT 0x04 and IN 0x85.  The normal requests are the known parameter
IDs 2 (focus mode), 27 (firmware version), and 28 (runtime flag).  The direct
Phocus write of parameter ID 2 is kept as a diagnostic experiment: stock X2D
firmware may reject AF-C at that layer even though the factory service accepts
it.  The intended AF-C operation uses the fixed factory HblShell path below
and is immediately verified by a readback; AF-S is provided only as a rollback.

The packet and response layout is based on the supplied 4.2.0 capture.  A
response can be split over several bulk transfers and may include trailing
transport padding; the reader collects the stream before validating it.

In addition to the Phocus parameter messages, the same USB control bulk
endpoints carry the public factory-diagnostic HblM channel used by the
WeiCheng97 tool over Wi-Fi.  The USB host node is 8 (the Wi-Fi TCP host is 9).
Only fixed, named HblShell operations are exposed here: the validated runtime
focus-mode write/readback and a guarded process-local AF-C menu-gate
experiment.  A separate read-only command-49 probe checks that the factory
channel responds before a write is attempted.  There is no arbitrary-shell
option.  Fixed runtime-only USB-gadget commands can also hand the connection
from this factory bulk interface to ADB and restore the production gadget.
They are dispatched through a delayed background shell so the factory reply
can finish before USB re-enumerates.  A camera restart restores the normal
focus-mode, menu-gate, and production USB-gadget state.
"""

from __future__ import annotations

import argparse
import re
import secrets
import struct
import sys
import time
from dataclasses import dataclass


DEFAULT_VID = 0x2756
DEFAULT_PID = 0x0009
DEFAULT_INTERFACE = 3
DEFAULT_ALTSETTING = 0
DEFAULT_OUT_ENDPOINT = 0x04
DEFAULT_IN_ENDPOINT = 0x85
DEFAULT_TIMEOUT_MS = 1500
MAX_BULK_READ = 1024
READ_PARAMETER = 0x02
WRITE_PARAMETER = 0x03
REPLY_PARAMETER = 0x82
ALLOWED_PARAMETERS = {
    2: "focus mode",
    27: "firmware version",
    28: "runtime flag",
}
FOCUS_MODE_NAMES = {
    0: "E_FocusModes_Man",
    1: "E_FocusModes_Afs",
    2: "E_FocusModes_Afc",
    3: "E_FocusModes_Aft",
}
WRITABLE_FOCUS_MODES = {
    "afs": 1,
    "afc": 2,
}

# Request and reply use different five-byte routing prefixes.  Both prefixes
# were observed on the same interface during one read-basics run:
#   parameter 27: 03 00 05 08 0c 01 00 82 ...
#   parameter 28: 03 00 05 08 05 01 00 82 ...
# Byte 2 is not a total USB-transfer length.
REPLY_ROUTE_PREFIXES = {
    bytes((0x03, 0x00, 0x05, 0x08, 0x0C)),
    bytes((0x03, 0x00, 0x05, 0x08, 0x05)),
}

# The msg2dbus/camera-test factory channel is the same 257-byte HblM frame used
# by the public Wi-Fi diagnostic tool, but both the host node and the receive
# signal are transport-specific.  USB uses node 8 and usbhost_testrx signal
# 0x000a; TCP/Wi-Fi uses node 9 and tcphost_testrx signal 0x0005.  Test replies
# use the common testtx signal 0x0009 and are routed back to the active host.
FACTORY_FRAME_SIZE = 257
FACTORY_COMMAND_SIZE = 252
FACTORY_COMMAND_DATA_SIZE = 232
FACTORY_SIGNAL_REQUEST = 0x000A
FACTORY_SIGNAL_RESPONSE = 0x0009
FACTORY_NODE_USBHOST = 8
FACTORY_NODE_EAGLE = 5
FACTORY_MESSAGE_TYPE = 0xFC
FACTORY_COMMAND_HBL_SHELL = 65
FACTORY_COMMAND_PROD_CONFIG = 49
FACTORY_FUNCTION_NOTIFICATION = 4
FACTORY_FUNCTION_GET = 2
FACTORY_FIELD_WIFI_REGION = 13
FACTORY_RESPONSE_HEADER = struct.pack(
    "<HBBB",
    FACTORY_SIGNAL_RESPONSE,
    FACTORY_NODE_EAGLE,
    FACTORY_NODE_USBHOST,
    FACTORY_MESSAGE_TYPE,
)
FACTORY_FOCUS_SET_COMMANDS = {
    "afc": (
        "/system/bin/odindb-send --print-cmdline -s camera -p focus_mode "
        "-- E_FocusModes_Afc 2>&1 || true"
    ),
    "afs": (
        "/system/bin/odindb-send --print-cmdline -s camera -p focus_mode "
        "-- E_FocusModes_Afs 2>&1 || true"
    ),
}
FACTORY_FOCUS_READ_COMMAND = (
    "/system/bin/odindb-send -s camera -p focus_mode 2>&1 || true"
)
EXPECTED_X2D_DEVICE = "eagle2_ec1706_native"
EXPECTED_CAMERA_GUI_SHA256 = (
    "16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0"
)
AFC_MENU_FILE_OFFSET = 0x018A2A64
FACTORY_GUI_MAP_PROBE = (
    "p=$(pidof camera-gui);echo pid=$p;"
    "grep -F '/system/bin/camera-gui' /proc/$p/maps 2>&1"
)
# Arm a short, bounded real-time watcher before asking init to start the GUI.
# The watcher sleeps between polls, so it cannot monopolize the CPU if startup
# fails.  Once the new executable is visible it stops the process, ideally
# before the compiled QML singleton is instantiated.  The command is kept
# below HblShell's 231-byte payload limit.
FACTORY_GUI_RESTART_STOP_EARLY = (
    "stop camera-gui;while pidof camera-gui;do :;done;"
    "timeout 5 chrt -f 99 sh -c 'until p=$(pidof camera-gui);"
    "do usleep 1000;done;kill -STOP $p'&"
    "start camera-gui;wait;p=$(pidof camera-gui);"
    "grep State /proc/$p/status 2>&1"
)
FACTORY_GUI_CONTINUE = "kill -CONT $(pidof camera-gui) 2>&1 || true"
FACTORY_GUI_STOCK_RESTART = (
    "stop camera-gui;while pidof camera-gui;do :;done;"
    "start camera-gui;sleep 2;echo pid=$(pidof camera-gui)"
)
FACTORY_GUI_STATE_PROBE = (
    "p=$(pidof camera-gui);grep State /proc/$p/status 2>&1"
)
FACTORY_USB_MODE_PROBE = (
    "for p in sys.usb.config sys.usb.state persist.sys.usb.config;"
    "do echo $p=$(getprop $p);done;echo adbd=$(pidof adbd);"
    "tr ' ' '\\n' </proc/cmdline|"
    "grep -E '^(mp_state|secure_debug)='||true"
)
# The delayed child survives the command-65 helper long enough to tear down
# and rebuild the gadget.  /dev/null avoids leaving a persistent marker or log
# on the camera.  Both commands are fixed and remain below the 231-byte limit.
FACTORY_ENABLE_USB_ADB_RUNTIME = (
    "/system/bin/toybox nohup /system/bin/sh -c 'sleep 1;"
    "setprop sys.usb.config none;sleep 1;"
    "setprop sys.usb.config rndis,mass_storage,bulk,acm,adb' "
    ">/dev/null 2>&1 &"
)
FACTORY_RESTORE_USB_NO_ADB_RUNTIME = (
    "/system/bin/toybox nohup /system/bin/sh -c 'sleep 1;"
    "setprop sys.usb.config none;sleep 1;"
    "setprop sys.usb.config rndis,mass_storage,bulk,acm' "
    ">/dev/null 2>&1 &"
)


class UsbFactoryError(Exception):
    """A dependency, enumeration, framing, or USB I/O failure."""


def crc16_xmodem(data: bytes, crc: int = 0) -> int:
    """Return the XMODEM CRC used by camera-test diagnostic frames."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_factory_shell_request(command: str, cookie: int) -> bytes:
    """Build one fixed-format command-65 HblShell request for USB node 8."""
    encoded = command.encode("utf-8")
    if len(encoded) >= FACTORY_COMMAND_DATA_SIZE:
        raise UsbFactoryError(
            f"factory command is too long ({len(encoded)} bytes; max 231)"
        )
    payload = bytearray(FACTORY_COMMAND_SIZE)
    struct.pack_into(
        "<III", payload, 0x00, FACTORY_COMMAND_HBL_SHELL, 0, cookie
    )
    # HblShell interprets this as the interval between output notifications.
    struct.pack_into("<I", payload, 0x10, 10)
    payload[0x14 : 0x14 + len(encoded)] = encoded
    struct.pack_into("<I", payload, 0x0C, crc16_xmodem(payload[0x10:0xFC]))
    return struct.pack(
        "<HBBB",
        FACTORY_SIGNAL_REQUEST,
        FACTORY_NODE_USBHOST,
        FACTORY_NODE_EAGLE,
        FACTORY_MESSAGE_TYPE,
    ) + bytes(payload)


def build_factory_prodconfig_get(cookie: int) -> bytes:
    """Build the public command-49 read-only factory probe."""
    payload = bytearray(FACTORY_COMMAND_SIZE)
    struct.pack_into(
        "<III",
        payload,
        0x00,
        FACTORY_COMMAND_PROD_CONFIG,
        FACTORY_FUNCTION_GET,
        cookie,
    )
    struct.pack_into("<I", payload, 0x14, FACTORY_FIELD_WIFI_REGION)
    struct.pack_into("<I", payload, 0x0C, crc16_xmodem(payload[0x10:0xFC]))
    return struct.pack(
        "<HBBB",
        FACTORY_SIGNAL_REQUEST,
        FACTORY_NODE_USBHOST,
        FACTORY_NODE_EAGLE,
        FACTORY_MESSAGE_TYPE,
    ) + bytes(payload)


def extract_factory_frames(buffer: bytearray) -> tuple[list[bytes], int]:
    """Extract CRC-valid 257-byte diagnostic responses from a padded stream."""
    frames: list[bytes] = []
    discarded = 0
    tail_size = len(FACTORY_RESPONSE_HEADER) - 1
    while True:
        start = buffer.find(FACTORY_RESPONSE_HEADER)
        if start < 0:
            retained = min(len(buffer), tail_size)
            drop = len(buffer) - retained
            if drop:
                del buffer[:drop]
                discarded += drop
            break
        if start:
            del buffer[:start]
            discarded += start
        if len(buffer) < FACTORY_FRAME_SIZE:
            break
        candidate = bytes(buffer[:FACTORY_FRAME_SIZE])
        payload = candidate[5:]
        stored_crc = struct.unpack_from("<I", payload, 0x0C)[0]
        calculated_crc = crc16_xmodem(payload[0x10:0xFC])
        if stored_crc != calculated_crc:
            del buffer[0]
            discarded += 1
            continue
        frames.append(candidate)
        del buffer[:FACTORY_FRAME_SIZE]
    return frames, discarded


@dataclass(frozen=True)
class FactoryResponse:
    command_id: int
    function: int
    cookie: int
    status: int
    text: str
    raw_frame: bytes


def parse_factory_response(frame: bytes) -> FactoryResponse:
    """Validate one factory response and decode its common command fields."""
    if len(frame) != FACTORY_FRAME_SIZE:
        raise UsbFactoryError(f"invalid factory response size: {len(frame)}")
    if frame[:5] != FACTORY_RESPONSE_HEADER:
        raise UsbFactoryError(
            "unexpected factory USB response header: " + frame[:10].hex(" ")
        )
    payload = frame[5:]
    command_id, function, cookie, stored_crc = struct.unpack_from(
        "<IIII", payload, 0
    )
    calculated_crc = crc16_xmodem(payload[0x10:0xFC])
    if stored_crc != calculated_crc:
        raise UsbFactoryError(
            f"bad factory response CRC: stored 0x{stored_crc:04x}, "
            f"calculated 0x{calculated_crc:04x}"
        )
    status = struct.unpack_from("<I", payload, 0x10)[0]
    text = payload[0x14:].split(b"\0", 1)[0].decode(
        "utf-8", errors="replace"
    )
    return FactoryResponse(command_id, function, cookie, status, text, frame)


def build_read_parameter(parameter_id: int, sequence: int = 1) -> bytes:
    """Build the documented ten-byte ReadParameter request."""
    if parameter_id not in ALLOWED_PARAMETERS:
        raise UsbFactoryError(
            "refusing unknown parameter ID "
            f"{parameter_id}; allowed IDs are {sorted(ALLOWED_PARAMETERS)}"
        )
    if not 0 <= sequence <= 0xFF:
        raise UsbFactoryError("request sequence must fit one byte")
    return bytes((0x04, 0x00, 0x08, 0x05, 0x05, sequence, 0x00, READ_PARAMETER)) + struct.pack(
        "<H", parameter_id
    )


def build_write_focus_mode(mode: int, sequence: int = 1) -> bytes:
    """Build the narrowly scoped WriteParameter request for parameter ID 2.

    ``WriteParameter::OnPhocusMessage`` in the shipped ``phocus`` binary
    consumes a two-byte little-endian parameter ID followed by the
    ``sCameraParameter`` textual scalar.  Focus mode therefore uses ``iN``;
    the frame's message type is the adjacent write value ``0x03``.
    """
    if mode not in WRITABLE_FOCUS_MODES.values():
        raise UsbFactoryError(
            "USB write is limited to 1 (AF-S) and 2 (AF-C); other focus modes are read-only"
        )
    if not 0 <= sequence <= 0xFF:
        raise UsbFactoryError("request sequence must fit one byte")
    payload = struct.pack("<H", 2) + f"i{mode}".encode("ascii")
    # The first four bytes are the request route used by ReadParameter.  The
    # fifth byte is the length of the inner PhocusMessage (sequence, type and
    # payload), not the length of the complete USB transfer.  A read of ID 2
    # is therefore ``... 05 01 00 02 02 00`` (five inner bytes); this write
    # has seven inner bytes (``02 00 i2`` as the payload).
    inner_length = 3 + len(payload)
    if inner_length > 0xFF:
        raise UsbFactoryError("focus-mode write message is unexpectedly long")
    return bytes(
        (0x04, 0x00, 0x08, 0x05, inner_length, sequence, 0x00, WRITE_PARAMETER)
    ) + payload


@dataclass(frozen=True)
class ParameterResponse:
    sequence: int
    parameter_id: int
    frame_length: int
    transport_length: int
    raw_frame: bytes
    value: bytes
    echoed_parameter_id: bool


def _logical_frame_length(transfer: bytes, parameter_id: int) -> int | None:
    """Return the end of the first parameter value in a collected stream."""
    if len(transfer) < 8:
        return None
    payload = transfer[8:]
    payload_offset = 8
    if len(payload) >= 2 and struct.unpack_from("<H", payload, 0)[0] == parameter_id:
        payload = payload[2:]
        payload_offset += 2
    if parameter_id == 27:
        nul = payload.find(b"\0")
        if nul >= 0:
            return payload_offset + nul + 1
        return None
    if parameter_id in (2, 28) and payload.startswith(b"i"):
        index = 1
        if index < len(payload) and payload[index] in (ord("+"), ord("-")):
            index += 1
        digit_start = index
        while index < len(payload) and 0x30 <= payload[index] <= 0x39:
            index += 1
        if index > digit_start and (index == len(payload) or payload[index] == 0):
            if index < len(payload) and payload[index] == 0:
                index += 1
            return payload_offset + index
    return None


def parse_parameter_response(
    transfer: bytes, parameter_id: int, sequence: int
) -> ParameterResponse:
    """Validate the observed route/sequence/type and extract one value.

    The camera can split the logical response across multiple bulk IN
    packets, and may add NUL padding to the final packet.  ``transfer`` is
    therefore the complete collected stream, not a single USB packet.
    """
    if len(transfer) < 10:
        raise UsbFactoryError(
            f"short USB response ({len(transfer)} bytes): {transfer.hex(' ')}"
        )
    if transfer[:5] not in REPLY_ROUTE_PREFIXES:
        raise UsbFactoryError(
            "unexpected USB response route/header: " + transfer[:10].hex(" ")
        )
    if transfer[5] != sequence:
        raise UsbFactoryError(
            f"response sequence mismatch: expected {sequence}, got {transfer[5]}"
        )
    if transfer[6] != 0x00:
        raise UsbFactoryError(f"unexpected response reserved byte 0x{transfer[6]:02x}")
    if transfer[7] != REPLY_PARAMETER:
        raise UsbFactoryError(
            f"unexpected response type 0x{transfer[7]:02x}; expected 0x{REPLY_PARAMETER:02x}"
        )

    # Stop at the first complete parameter field.  A longer bulk transfer can
    # contain asynchronous data after that field; it is not part of this
    # response.  If no typed field is recognizable, retain the non-padding
    # bytes for diagnostics.
    logical_length = _logical_frame_length(transfer, parameter_id)
    frame = bytes(transfer[:logical_length]) if logical_length else bytes(transfer).rstrip(b"\0")
    frame_length = len(frame)
    transport_length = len(transfer)
    payload = frame[8:]
    echoed = len(payload) >= 2 and struct.unpack_from("<H", payload)[0] == parameter_id
    if echoed:
        payload = payload[2:]
    value = payload.split(b"\0", 1)[0]
    return ParameterResponse(
        sequence=sequence,
        parameter_id=parameter_id,
        frame_length=frame_length,
        transport_length=transport_length,
        raw_frame=frame,
        value=value,
        echoed_parameter_id=echoed,
    )


def format_parameter_value(parameter_id: int, value: bytes) -> str:
    """Decode the observed Phocus scalar prefix and retain its raw spelling."""
    trimmed = value.rstrip(b"\0")
    if parameter_id == 27:
        match = re.fullmatch(rb"S([0-9]+),(.*)", trimmed, flags=re.DOTALL)
        if match:
            declared = int(match.group(1))
            text_bytes = match.group(2)
            if declared == len(text_bytes):
                try:
                    text = text_bytes.decode("ascii")
                except UnicodeDecodeError:
                    text = ""
                if text:
                    return f"text={text!r} encoding=S{declared}, raw={trimmed.hex(' ')}"
        try:
            text = trimmed.decode("ascii")
        except UnicodeDecodeError:
            text = ""
        if text and all(0x20 <= byte < 0x7F for byte in trimmed):
            return f"text={text!r} hex={trimmed.hex(' ')}"
    if parameter_id in (2, 28):
        match = re.fullmatch(rb"i(-?[0-9]+)", trimmed)
        if match:
            integer = int(match.group(1))
            enum = ""
            if parameter_id == 2 and integer in FOCUS_MODE_NAMES:
                enum = f" enum={FOCUS_MODE_NAMES[integer]}"
            return f"integer={integer}{enum} encoding=i raw={trimmed.hex(' ')}"
        if len(trimmed) in (1, 2, 4, 8):
            return f"integer={int.from_bytes(trimmed, 'little')} hex={trimmed.hex(' ')}"
    return f"hex={trimmed.hex(' ')}"


def parse_gui_executable_mapping(output: str) -> tuple[int, int]:
    """Return the known offset-zero executable camera-gui mapping."""
    match = re.search(
        r"(?m)^([0-9a-f]+)-([0-9a-f]+)\s+r-xp\s+00000000\s+"
        r"\S+\s+\d+\s+/system/bin/camera-gui\s*$",
        output,
    )
    if not match:
        raise UsbFactoryError(
            "cannot find the offset-zero executable camera-gui mapping:\n"
            + output.rstrip()
        )
    start, end = (int(value, 16) for value in match.groups())
    target = start + AFC_MENU_FILE_OFFSET
    if start >= end or target < start or target + 4 > end:
        raise UsbFactoryError(
            "CameraUI.canChangeAfc offset falls outside the executable mapping"
        )
    return start, end


def parse_four_hex_bytes(output: str) -> bytes:
    """Parse one strict four-byte od output line."""
    match = re.search(
        r"(?mi)^\s*([0-9a-f]{2})\s+([0-9a-f]{2})\s+"
        r"([0-9a-f]{2})\s+([0-9a-f]{2})\s*$",
        output,
    )
    if not match:
        raise UsbFactoryError(
            "cannot parse four camera-gui process bytes:\n" + output.rstrip()
        )
    return bytes(int(value, 16) for value in match.groups())


def build_factory_process_memory_read(address: int) -> str:
    """Build the fixed four-byte gate read using a host-validated address."""
    if address < 0:
        raise UsbFactoryError("invalid camera-gui process address")
    return (
        "p=$(pidof camera-gui);"
        f"od -An -tx1 -N4 -j {address} /proc/$p/mem 2>&1"
    )


def build_factory_process_memory_write(address: int, value: int) -> str:
    """Build the constrained one-byte gate write using a decimal address."""
    if address < 0 or value not in (0, 1):
        raise UsbFactoryError("invalid camera-gui process-memory write")
    return (
        "p=$(pidof camera-gui);"
        f"printf '\\{value:03o}'|dd of=/proc/$p/mem bs=1 "
        f"seek={address} count=1 2>&1"
    )


def _load_usb():
    try:
        import usb.core  # type: ignore
        import usb.util  # type: ignore
    except ImportError as error:
        raise UsbFactoryError(
            "PyUSB is not installed; install pyusb and a libusb backend before "
            "using the direct factory USB reader"
        ) from error
    return usb.core, usb.util


class FactoryUsbReader:
    def __init__(
        self,
        vid: int,
        pid: int,
        interface: int,
        altsetting: int,
        out_endpoint: int,
        in_endpoint: int,
        timeout_ms: int,
    ) -> None:
        self.vid = vid
        self.pid = pid
        self.interface = interface
        self.altsetting = altsetting
        self.out_endpoint = out_endpoint
        self.in_endpoint = in_endpoint
        self.timeout_ms = timeout_ms
        self.core, self.util = _load_usb()
        self.device = None
        self.out_ep = None
        self.in_ep = None
        self.last_factory_transport_bytes = 0
        self.last_factory_discarded_bytes = 0
        self.last_factory_preview = b""

    def __enter__(self) -> "FactoryUsbReader":
        try:
            devices = list(
                self.core.find(
                    find_all=True,
                    idVendor=self.vid,
                    idProduct=self.pid,
                )
                or []
            )
        except Exception as error:
            raise UsbFactoryError(
                f"PyUSB could not access a libusb backend: {error}; install libusb"
            ) from error
        if not devices:
            raise UsbFactoryError(
                f"USB camera {self.vid:04x}:{self.pid:04x} was not enumerated; "
                "check the data cable, camera USB mode, and system_profiler SPUSBDataType"
            )
        if len(devices) > 1:
            raise UsbFactoryError(
                f"found {len(devices)} matching USB devices; disconnect other 2756:{self.pid:04x} devices"
            )
        self.device = devices[0]
        try:
            self.device.set_configuration()
        except Exception:
            # A configuration can already be active; descriptor access below
            # is still useful and claim_interface will report a real failure.
            pass
        try:
            self.util.claim_interface(self.device, self.interface)
            self.device.set_interface_altsetting(
                interface=self.interface,
                alternate_setting=self.altsetting,
            )
            config = self.device.get_active_configuration()
            intf = self.util.find_descriptor(
                config,
                bInterfaceNumber=self.interface,
                bAlternateSetting=self.altsetting,
            )
            if intf is None:
                raise UsbFactoryError(
                    f"interface {self.interface} alt {self.altsetting} not present"
                )
            self.out_ep = self.util.find_descriptor(
                intf, bEndpointAddress=self.out_endpoint
            )
            self.in_ep = self.util.find_descriptor(
                intf, bEndpointAddress=self.in_endpoint
            )
            if self.out_ep is None or self.in_ep is None:
                raise UsbFactoryError(
                    f"expected endpoints OUT 0x{self.out_endpoint:02x} and "
                    f"IN 0x{self.in_endpoint:02x} were not found"
                )
        except UsbFactoryError:
            self.close()
            raise
        except Exception as error:
            self.close()
            raise UsbFactoryError(f"could not claim factory USB interface: {error}") from error
        return self

    def close(self) -> None:
        device = self.device
        self.device = None
        self.out_ep = None
        self.in_ep = None
        if device is not None:
            try:
                # release_interface alone leaves the device handle open. WinUSB
                # can deny the next reader even while the old interface is released.
                # Explicit disposal also closes the handle; do not rely on GC.
                self.util.dispose_resources(device)
            except Exception:
                pass

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def read_parameter(self, parameter_id: int, sequence: int = 1) -> ParameterResponse:
        if self.out_ep is None or self.in_ep is None:
            raise UsbFactoryError("USB interface is not open")
        request = build_read_parameter(parameter_id, sequence)
        try:
            written = self.out_ep.write(request, timeout=self.timeout_ms)
            if written != len(request):
                raise UsbFactoryError(
                    f"short USB write: {written}/{len(request)} bytes"
                )
            transfer = self._read_response_transfer(parameter_id)
        except UsbFactoryError:
            raise
        except Exception as error:
            raise UsbFactoryError(f"USB parameter read failed: {error}") from error
        return parse_parameter_response(transfer, parameter_id, sequence)

    def write_focus_mode(self, mode: int, sequence: int = 1) -> bytes:
        """Write only focus-mode ID 2 and return any immediate transport reply.

        The reply opcode is not treated as a parameter value here.  The
        authoritative check is the subsequent ID-2 readback, which avoids
        guessing at an undocumented error/result payload.
        """
        if self.out_ep is None or self.in_ep is None:
            raise UsbFactoryError("USB interface is not open")
        request = build_write_focus_mode(mode, sequence)
        try:
            # A previous asynchronous notification must not be mistaken for
            # the write result or the following readback.
            self._drain_transport(50)
            written = self.out_ep.write(request, timeout=self.timeout_ms)
            if written != len(request):
                raise UsbFactoryError(
                    f"short USB write: {written}/{len(request)} bytes"
                )
            return self._drain_transport(min(self.timeout_ms, 500))
        except UsbFactoryError:
            raise
        except Exception as error:
            raise UsbFactoryError(f"USB focus-mode write failed: {error}") from error

    def _capture_factory_frames(
        self, request: bytes, cookie: int, capture_ms: int = 2500
    ) -> list[FactoryResponse]:
        """Send one command-49/65 frame and collect matching USB responses."""
        if self.out_ep is None or self.in_ep is None:
            raise UsbFactoryError("USB interface is not open")
        if len(request) != FACTORY_FRAME_SIZE:
            raise UsbFactoryError(
                f"invalid factory request size: {len(request)}"
            )
        try:
            self._drain_transport(50)
            written = self.out_ep.write(request, timeout=self.timeout_ms)
            if written != len(request):
                raise UsbFactoryError(
                    f"short factory USB write: {written}/{len(request)} bytes"
                )
            buffer = bytearray()
            responses: list[FactoryResponse] = []
            transport_bytes = 0
            discarded_bytes = 0
            preview = bytearray()
            deadline = time.monotonic() + (capture_ms / 1000.0)
            while time.monotonic() < deadline:
                remaining_ms = max(
                    1, int((deadline - time.monotonic()) * 1000)
                )
                try:
                    chunk = bytes(
                        self.in_ep.read(
                            MAX_BULK_READ,
                            timeout=min(self.timeout_ms, remaining_ms),
                        )
                    )
                except Exception as error:
                    if self._is_timeout(error):
                        if responses:
                            break
                        continue
                    raise UsbFactoryError(
                        f"factory USB bulk read failed: {error}"
                    ) from error
                if not chunk:
                    break
                transport_bytes += len(chunk)
                if len(preview) < 64:
                    preview.extend(chunk[: 64 - len(preview)])
                buffer.extend(chunk)
                frames, discarded = extract_factory_frames(buffer)
                discarded_bytes += discarded
                for frame in frames:
                    response = parse_factory_response(frame)
                    if response.cookie == cookie:
                        responses.append(response)
                # A normal command-49 response is one frame.  HblShell has a
                # notification stream and a final frame, so keep collecting.
                if responses and request[5:9] != struct.pack(
                    "<I", FACTORY_COMMAND_HBL_SHELL
                ):
                    break
            self.last_factory_transport_bytes = transport_bytes
            self.last_factory_discarded_bytes = discarded_bytes
            self.last_factory_preview = bytes(preview)
            return responses
        except UsbFactoryError:
            raise
        except Exception as error:
            raise UsbFactoryError(f"factory USB exchange failed: {error}") from error

    def factory_prodconfig_get(self) -> FactoryResponse:
        """Read the public wifiRegion field without changing camera state."""
        cookie = secrets.randbits(32) or 1
        responses = self._capture_factory_frames(
            build_factory_prodconfig_get(cookie), cookie
        )
        if not responses:
            details = (
                f"; received {self.last_factory_transport_bytes} transport byte(s), "
                f"discarded {self.last_factory_discarded_bytes} byte(s)"
            )
            if self.last_factory_preview:
                details += "; first bytes: " + self.last_factory_preview.hex(" ")
            raise UsbFactoryError(
                "no validated response to USB factory command 49"
                + details
                + "; check that the camera is awake and the bulk control channel is available"
            )
        return responses[-1]

    def factory_shell(self, command: str, capture_ms: int | None = None) -> str:
        """Run one allowlisted command-65 request and return its output."""
        cookie = secrets.randbits(32) or 1
        request = build_factory_shell_request(command, cookie)
        if self.out_ep is None or self.in_ep is None:
            raise UsbFactoryError("USB interface is not open")
        try:
            self._drain_transport(50)
            written = self.out_ep.write(request, timeout=self.timeout_ms)
            if written != len(request):
                raise UsbFactoryError(
                    f"short HblShell USB write: {written}/{len(request)} bytes"
                )
            buffer = bytearray()
            output: list[str] = []
            capture_ms = capture_ms if capture_ms is not None else self.timeout_ms
            deadline = time.monotonic() + (capture_ms / 1000.0)
            while time.monotonic() < deadline:
                remaining_ms = max(
                    1, int((deadline - time.monotonic()) * 1000)
                )
                try:
                    chunk = bytes(
                        self.in_ep.read(
                            MAX_BULK_READ,
                            timeout=min(self.timeout_ms, remaining_ms),
                        )
                    )
                except Exception as error:
                    if self._is_timeout(error):
                        continue
                    raise UsbFactoryError(
                        f"HblShell USB bulk read failed: {error}"
                    ) from error
                if not chunk:
                    continue
                buffer.extend(chunk)
                frames, _discarded = extract_factory_frames(buffer)
                for frame in frames:
                    response = parse_factory_response(frame)
                    if (
                        response.command_id != FACTORY_COMMAND_HBL_SHELL
                        or response.cookie != cookie
                    ):
                        continue
                    if response.function == FACTORY_FUNCTION_NOTIFICATION:
                        output.append(response.text)
                        continue
                    if response.status != 0:
                        raise UsbFactoryError(
                            f"USB HblShell command failed with status "
                            f"{response.status}: {command}\n"
                            f"{''.join(output).rstrip()}"
                        )
                    return "".join(output).rstrip("\0")
            raise UsbFactoryError(
                f"timed out waiting for USB HblShell result: {command}"
            )
        except UsbFactoryError:
            raise
        except Exception as error:
            raise UsbFactoryError(f"USB HblShell exchange failed: {error}") from error

    @staticmethod
    def _is_timeout(error: BaseException) -> bool:
        errno = getattr(error, "errno", None)
        if errno in (60, 110):  # macOS / Linux timeout values
            return True
        text = str(error).lower()
        return "timed out" in text or "timeout" in text

    def _read_response_transfer(self, parameter_id: int) -> bytes:
        """Collect one possibly split reply without consuming the next event."""
        chunks = bytearray()
        deadline = time.monotonic() + (self.timeout_ms / 1000.0)
        while len(chunks) < MAX_BULK_READ:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            try:
                chunk = bytes(
                    self.in_ep.read(
                        MAX_BULK_READ - len(chunks), timeout=remaining_ms
                    )
                )
            except Exception as error:
                # Once at least one packet arrived, an IN timeout is the
                # normal end-of-frame condition on this interface.
                if chunks and self._is_timeout(error):
                    break
                raise UsbFactoryError(f"USB bulk read failed: {error}") from error
            if not chunk:
                break
            chunks.extend(chunk)
            logical_length = _logical_frame_length(bytes(chunks), parameter_id)
            if logical_length is not None:
                return bytes(chunks[:logical_length])
        if not chunks:
            raise UsbFactoryError("empty USB response")
        return bytes(chunks)

    def _drain_transport(self, timeout_ms: int) -> bytes:
        """Collect currently queued IN data until a short idle timeout."""
        if self.in_ep is None:
            raise UsbFactoryError("USB interface is not open")
        chunks = bytearray()
        deadline = time.monotonic() + (max(1, timeout_ms) / 1000.0)
        while len(chunks) < MAX_BULK_READ:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            try:
                chunk = bytes(
                    self.in_ep.read(
                        MAX_BULK_READ - len(chunks), timeout=remaining_ms
                    )
                )
            except Exception as error:
                if self._is_timeout(error):
                    break
                raise UsbFactoryError(f"USB bulk drain failed: {error}") from error
            if not chunk:
                break
            chunks.extend(chunk)
        return bytes(chunks)


def validate_factory_gui_target(reader: FactoryUsbReader) -> tuple[str, str]:
    """Require the exact X2D 4.2.0 target before touching process memory."""
    device_output = reader.factory_shell("getprop ro.product.device")
    device = device_output.strip().splitlines()[-1] if device_output.strip() else ""
    if device != EXPECTED_X2D_DEVICE:
        raise UsbFactoryError(
            f"unexpected camera target {device!r}; expected {EXPECTED_X2D_DEVICE!r}"
        )
    hash_output = reader.factory_shell("sha256sum /system/bin/camera-gui")
    match = re.search(r"(?i)\b([0-9a-f]{64})\b", hash_output)
    if not match:
        raise UsbFactoryError(
            "cannot parse /system/bin/camera-gui SHA-256:\n" + hash_output.rstrip()
        )
    gui_hash = match.group(1).lower()
    if gui_hash != EXPECTED_CAMERA_GUI_SHA256:
        raise UsbFactoryError(
            "unknown /system/bin/camera-gui; refusing process-memory write: "
            + gui_hash
        )
    return device, gui_hash


def run_factory_usb_mode_probe(reader: FactoryUsbReader) -> None:
    """Report the active gadget and production/debug boot flags read-only."""
    device, gui_hash = validate_factory_gui_target(reader)
    output = reader.factory_shell(FACTORY_USB_MODE_PROBE)
    print(f"target:            {device}")
    print(f"camera-gui SHA-256: {gui_hash}")
    print("operation:         read-only USB gadget state probe")
    print(output.rstrip() or "(no output)")


def run_factory_set_usb_adb_runtime(
    reader: FactoryUsbReader, enabled: bool
) -> None:
    """Dispatch a delayed, runtime-only gadget switch over factory USB."""
    device, gui_hash = validate_factory_gui_target(reader)
    command = (
        FACTORY_ENABLE_USB_ADB_RUNTIME
        if enabled
        else FACTORY_RESTORE_USB_NO_ADB_RUNTIME
    )
    desired = (
        "rndis,mass_storage,bulk,acm,adb"
        if enabled
        else "rndis,mass_storage,bulk,acm"
    )
    print(f"target:            {device}")
    print(f"camera-gui SHA-256: {gui_hash}")
    print(
        "operation:         "
        + ("enable USB ADB" if enabled else "restore stock USB without ADB")
        + " (runtime only)"
    )
    print(f"requested gadget:  {desired}")
    output = reader.factory_shell(command, capture_ms=max(reader.timeout_ms, 2500))
    if output.strip():
        print(output.rstrip())
    print("dispatch:          accepted; USB will re-enumerate after about 2 seconds")
    print("persistence:       a camera reboot restores the production gadget")
    if enabled:
        print("next:              wait 3-6 seconds, then run 'adb devices -l'")
    else:
        print("next:              wait 3-6 seconds for factory USB to return")


def get_factory_afc_menu_gate(
    reader: FactoryUsbReader,
) -> tuple[int, int, bytes, str]:
    """Resolve and read CameraUI.canChangeAfc from the running GUI."""
    mapping_output = reader.factory_shell(FACTORY_GUI_MAP_PROBE)
    mapping_start, mapping_end = parse_gui_executable_mapping(mapping_output)
    address = mapping_start + AFC_MENU_FILE_OFFSET
    read_output = reader.factory_shell(build_factory_process_memory_read(address))
    return address, mapping_end, parse_four_hex_bytes(read_output), mapping_output


def run_factory_afc_menu_probe(reader: FactoryUsbReader) -> None:
    """Read the process-local AF-C menu gate without changing camera state."""
    device, gui_hash = validate_factory_gui_target(reader)
    address, mapping_end, gate, mapping_output = get_factory_afc_menu_gate(reader)
    print(f"target:            {device}")
    print(f"camera-gui SHA-256: {gui_hash}")
    print("operation:         read-only USB CameraUI.canChangeAfc probe")
    print(mapping_output.rstrip())
    print(f"validated target:  0x{address:x} (< 0x{mapping_end:x})")
    print(f"gate:              {gate.hex(' ')}")


def run_factory_enable_afc_menu_early(reader: FactoryUsbReader) -> None:
    """Restart, stop early, patch the gate, and always resume camera-gui."""
    device, gui_hash = validate_factory_gui_target(reader)
    restart_attempted = False
    stopped = False
    try:
        restart_attempted = True
        state_output = reader.factory_shell(
            FACTORY_GUI_RESTART_STOP_EARLY,
            capture_ms=max(reader.timeout_ms, 7000),
        )
        if not re.search(r"(?m)^State:\s+T\b", state_output):
            raise UsbFactoryError(
                "new camera-gui was not confirmed stopped; refusing memory write:\n"
                + state_output.rstrip()
            )
        stopped = True
        address, mapping_end, before, mapping_output = get_factory_afc_menu_gate(
            reader
        )
        stock = bytes.fromhex("00 00 00 00")
        patched = bytes.fromhex("01 00 00 00")
        if before not in (stock, patched):
            raise UsbFactoryError(
                "unexpected CameraUI.canChangeAfc bytes; refusing write: "
                + before.hex(" ")
            )

        print(f"target:            {device}")
        print(f"camera-gui SHA-256: {gui_hash}")
        print("operation:         early runtime AF-C menu gate patch over USB")
        print("process state:     T (stopped)")
        print(mapping_output.rstrip())
        print(f"address:           0x{address:x} (< 0x{mapping_end:x})")
        print(f"before:            {before.hex(' ')}")
        if before != patched:
            write_output = reader.factory_shell(
                build_factory_process_memory_write(address, 1)
            )
            if write_output.strip():
                print(write_output.rstrip())
        _, _, after, _ = get_factory_afc_menu_gate(reader)
        if after != patched:
            raise UsbFactoryError(
                "process-memory readback mismatch: expected 01 00 00 00, got "
                + after.hex(" ")
            )
        print(f"after:             {after.hex(' ')}")
    finally:
        if restart_attempted:
            try:
                continue_output = reader.factory_shell(FACTORY_GUI_CONTINUE)
                if continue_output.strip():
                    print(continue_output.rstrip())
            except UsbFactoryError as error:
                print(
                    "warning: could not confirm camera-gui SIGCONT: " + str(error),
                    file=sys.stderr,
                )
    if not stopped:
        raise UsbFactoryError("camera-gui early-stop sequence did not complete")
    state_output = reader.factory_shell(FACTORY_GUI_STATE_PROBE)
    print("after resume:      " + (state_output.strip() or "(no state output)"))
    if re.search(r"(?m)^State:\s+T\b", state_output):
        raise UsbFactoryError(
            "camera-gui is still stopped after SIGCONT; reboot the camera to recover"
        )
    print("persistence:       GUI restart or camera reboot restores the stock gate")
    print("next:              open Focus Mode and check whether AF-C is now selectable")


def run_factory_restore_afc_menu(reader: FactoryUsbReader) -> None:
    """Restart the unmodified stock GUI and verify that its gate is false."""
    device, gui_hash = validate_factory_gui_target(reader)
    restart_output = reader.factory_shell(
        FACTORY_GUI_STOCK_RESTART,
        capture_ms=max(reader.timeout_ms, 5000),
    )
    address, _mapping_end, gate, _mapping_output = get_factory_afc_menu_gate(reader)
    if gate != bytes.fromhex("00 00 00 00"):
        raise UsbFactoryError(
            "stock GUI restart did not restore the gate to 00 00 00 00; got "
            + gate.hex(" ")
        )
    print(f"target:            {device}")
    print(f"camera-gui SHA-256: {gui_hash}")
    print("operation:         restart unmodified stock camera-gui")
    print(restart_output.rstrip() or "(no restart output)")
    print(f"address:           0x{address:x}")
    print(f"gate:              {gate.hex(' ')}")
    print("result:            stock AF-C menu gate restored")


def describe_devices(vid: int, pid: int) -> None:
    core, _util = _load_usb()
    try:
        devices = list(core.find(find_all=True, idVendor=vid, idProduct=pid) or [])
    except Exception as error:
        raise UsbFactoryError(
            f"PyUSB could not access a libusb backend: {error}; install libusb"
        ) from error
    if not devices:
        print(f"no matching USB device {vid:04x}:{pid:04x}")
        return
    for index, device in enumerate(devices, start=1):
        print(
            f"[{index}] {vid:04x}:{pid:04x} bus={getattr(device, 'bus', '?')} "
            f"address={getattr(device, 'address', '?')}"
        )
        try:
            for config in device:
                for intf in config:
                    endpoints = " ".join(
                        f"0x{ep.bEndpointAddress:02x}" for ep in intf
                    )
                    print(
                        f"  interface={intf.bInterfaceNumber} alt={intf.bAlternateSetting} "
                        f"class=0x{intf.bInterfaceClass:02x} endpoints={endpoints}"
                    )
        except Exception as error:
            print(f"  descriptor read failed: {error}")


def self_test() -> None:
    request_27 = build_read_parameter(27, 1)
    if request_27 != bytes.fromhex("04 00 08 05 05 01 00 02 1b 00"):
        raise UsbFactoryError(f"ID 27 request mismatch: {request_27.hex(' ')}")
    request_28 = build_read_parameter(28, 1)
    if request_28 != bytes.fromhex("04 00 08 05 05 01 00 02 1c 00"):
        raise UsbFactoryError(f"ID 28 request mismatch: {request_28.hex(' ')}")
    request_2 = build_read_parameter(2, 1)
    if request_2 != bytes.fromhex("04 00 08 05 05 01 00 02 02 00"):
        raise UsbFactoryError(f"ID 2 request mismatch: {request_2.hex(' ')}")
    write_afc = build_write_focus_mode(2, 1)
    if write_afc != bytes.fromhex("04 00 08 05 07 01 00 03 02 00 69 32"):
        raise UsbFactoryError(f"AF-C write request mismatch: {write_afc.hex(' ')}")
    factory_cookie = 0x12345678
    factory_probe = build_factory_prodconfig_get(factory_cookie)
    if factory_probe[:5] != bytes.fromhex("0a 00 08 05 fc"):
        raise UsbFactoryError(
            f"USB factory route mismatch: {factory_probe[:5].hex(' ')}"
        )
    if len(factory_probe) != FACTORY_FRAME_SIZE:
        raise UsbFactoryError("USB factory request length mismatch")
    factory_shell = build_factory_shell_request(
        "getprop ro.product.device", factory_cookie
    )
    if factory_shell[:5] != bytes.fromhex("0a 00 08 05 fc"):
        raise UsbFactoryError("USB HblShell route mismatch")
    synthetic = bytearray(FACTORY_FRAME_SIZE)
    synthetic[:5] = FACTORY_RESPONSE_HEADER
    response_payload = memoryview(synthetic)[5:]
    struct.pack_into(
        "<IIII", response_payload, 0, FACTORY_COMMAND_HBL_SHELL,
        FACTORY_FUNCTION_NOTIFICATION, factory_cookie, 0
    )
    response_payload[0x14 : 0x14 + 6] = b"eagle2"
    struct.pack_into(
        "<I", response_payload, 0x0C,
        crc16_xmodem(response_payload[0x10:0xFC])
    )
    parsed_factory = parse_factory_response(bytes(synthetic))
    if parsed_factory.text != "eagle2":
        raise UsbFactoryError("USB factory response parser self-test failed")
    value = b"S6,v4.2.0\0"
    frame = bytes((0x03, 0x00, 0x05, 0x08, 0x0C)) + bytes((1, 0, REPLY_PARAMETER))
    frame += struct.pack("<H", 27) + value
    padded = frame + bytes(MAX_BULK_READ - len(frame))
    parsed = parse_parameter_response(padded, 27, 1)
    if parsed.value != value.rstrip(b"\0") or parsed.frame_length != len(frame):
        raise UsbFactoryError("response parser self-test failed")
    frame_28 = bytes((0x03, 0x00, 0x05, 0x08, 0x05)) + bytes((1, 0, REPLY_PARAMETER)) + b"i1"
    parsed_28 = parse_parameter_response(frame_28, 28, 1)
    if parsed_28.value != b"i1" or format_parameter_value(28, parsed_28.value).split()[0] != "integer=1":
        raise UsbFactoryError("ID 28 route/value parser self-test failed")
    frame_2 = bytes((0x03, 0x00, 0x05, 0x08, 0x05)) + bytes((1, 0, REPLY_PARAMETER)) + b"i2"
    parsed_2 = parse_parameter_response(frame_2, 2, 1)
    if parsed_2.value != b"i2" or "E_FocusModes_Afc" not in format_parameter_value(2, parsed_2.value):
        raise UsbFactoryError("ID 2 focus-mode parser self-test failed")
    sample_mapping = (
        "pid=364\n"
        "5779877000-577b90d000 r-xp 00000000 103:08 166 "
        "/system/bin/camera-gui\n"
    )
    mapping_start, mapping_end = parse_gui_executable_mapping(sample_mapping)
    if (
        mapping_start != 0x5779877000
        or mapping_end != 0x577B90D000
        or mapping_start + AFC_MENU_FILE_OFFSET != 0x577B119A64
    ):
        raise UsbFactoryError("camera-gui mapping/address self-test failed")
    if parse_four_hex_bytes(" 01 00 00 00\n") != bytes.fromhex("01 00 00 00"):
        raise UsbFactoryError("camera-gui gate parser self-test failed")
    menu_commands = (
        FACTORY_GUI_MAP_PROBE,
        FACTORY_GUI_RESTART_STOP_EARLY,
        FACTORY_GUI_CONTINUE,
        FACTORY_GUI_STOCK_RESTART,
        FACTORY_GUI_STATE_PROBE,
        FACTORY_USB_MODE_PROBE,
        FACTORY_ENABLE_USB_ADB_RUNTIME,
        FACTORY_RESTORE_USB_NO_ADB_RUNTIME,
        build_factory_process_memory_read(0x577B119A64),
        build_factory_process_memory_write(0x577B119A64, 1),
    )
    for command in menu_commands:
        build_factory_shell_request(command, factory_cookie)
    if (
        len(FACTORY_GUI_RESTART_STOP_EARLY) >= FACTORY_COMMAND_DATA_SIZE
        or "timeout 5" not in FACTORY_GUI_RESTART_STOP_EARLY
        or "usleep 1000" not in FACTORY_GUI_RESTART_STOP_EARLY
    ):
        raise UsbFactoryError("bounded early-stop command self-test failed")
    print(
        "factory USB self-test: OK (ID 2/27/28 routes, focus-mode enum, "
        "S/i values, runtime write frames, USB command-49/65 route, "
        "split/padded parser, guarded early camera-gui gate patch, "
        "delayed runtime USB-ADB handoff)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vid", type=lambda value: int(value, 0), default=DEFAULT_VID)
    parser.add_argument("--pid", type=lambda value: int(value, 0), default=DEFAULT_PID)
    parser.add_argument("--interface", type=int, default=DEFAULT_INTERFACE)
    parser.add_argument("--altsetting", type=int, default=DEFAULT_ALTSETTING)
    parser.add_argument(
        "--out-endpoint",
        type=lambda value: int(value, 0),
        default=DEFAULT_OUT_ENDPOINT,
    )
    parser.add_argument(
        "--in-endpoint",
        type=lambda value: int(value, 0),
        default=DEFAULT_IN_ENDPOINT,
    )
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="validate the known request and response layout")
    commands.add_parser("enumerate", help="list matching USB descriptors and endpoints")
    commands.add_parser("read-basics", help="read only parameter IDs 27 and 28 once each")
    commands.add_parser("read-focus-mode", help="read only parameter ID 2 (AF-S/AF-C/MF/AFT)")
    set_mode = commands.add_parser(
        "set-focus-mode",
        help="experimental runtime-only write of parameter ID 2, followed by readback",
    )
    set_mode.add_argument(
        "mode",
        choices=tuple(WRITABLE_FOCUS_MODES),
        help="focus mode to request; only AF-S/AF-C are writable; restart restores state",
    )
    commands.add_parser(
        "set-afc-runtime",
        help="experimental shortcut for set-focus-mode afc (runtime only)",
    )
    commands.add_parser(
        "restore-afs-runtime",
        help="experimental shortcut for set-focus-mode afs (runtime only)",
    )
    commands.add_parser(
        "factory-probe",
        help="read-only USB factory command-49 probe (wifiRegion)",
    )
    commands.add_parser(
        "factory-usb-mode-probe",
        help="read-only gadget state and production/debug boot-flag probe",
    )
    commands.add_parser(
        "factory-enable-usb-adb-runtime",
        help=(
            "temporarily switch the USB gadget to include ADB; USB "
            "re-enumerates and a reboot restores production mode"
        ),
    )
    commands.add_parser(
        "factory-restore-usb-no-adb-runtime",
        help="temporarily restore the stock USB gadget without ADB",
    )
    commands.add_parser(
        "factory-set-afc-runtime",
        help=(
            "use the public command-65 factory channel to request AF-C "
            "through odindb-send, then read it back"
        ),
    )
    commands.add_parser(
        "factory-restore-afs-runtime",
        help="use command 65 to restore AF-S through odindb-send",
    )
    commands.add_parser(
        "factory-afc-menu-probe",
        help="read CameraUI.canChangeAfc from camera-gui over USB without writing",
    )
    commands.add_parser(
        "factory-enable-afc-menu-early-runtime",
        help=(
            "restart camera-gui, stop it early, patch CameraUI.canChangeAfc "
            "in process memory, and resume it"
        ),
    )
    commands.add_parser(
        "factory-restore-afc-menu-runtime",
        help="restart the unmodified stock camera-gui and verify the gate is false",
    )
    read_one = commands.add_parser("read", help="read one allowed parameter ID")
    read_one.add_argument("parameter", type=int, choices=sorted(ALLOWED_PARAMETERS))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "self-test":
        self_test()
        return 0
    if args.command == "enumerate":
        describe_devices(args.vid, args.pid)
        return 0
    with FactoryUsbReader(
        args.vid,
        args.pid,
        args.interface,
        args.altsetting,
        args.out_endpoint,
        args.in_endpoint,
        args.timeout_ms,
    ) as reader:
        if args.command == "factory-probe":
            response = reader.factory_prodconfig_get()
            body = response.raw_frame[5:]
            field, value = struct.unpack_from("<II", body, 0x14)
            print("operation: read-only USB factory command 49 ProdConfig get")
            print(
                f"  command={response.command_id} function={response.function} "
                f"cookie=0x{response.cookie:08x} status=0x{response.status:08x}"
            )
            print(f"  field={field} value={value}")
            print(f"  frame[0:{len(response.raw_frame)}]: {response.raw_frame.hex(' ')}")
            return 0
        if args.command == "factory-usb-mode-probe":
            run_factory_usb_mode_probe(reader)
            return 0
        if args.command == "factory-enable-usb-adb-runtime":
            run_factory_set_usb_adb_runtime(reader, enabled=True)
            return 0
        if args.command == "factory-restore-usb-no-adb-runtime":
            run_factory_set_usb_adb_runtime(reader, enabled=False)
            return 0
        if args.command == "factory-afc-menu-probe":
            run_factory_afc_menu_probe(reader)
            return 0
        if args.command == "factory-enable-afc-menu-early-runtime":
            run_factory_enable_afc_menu_early(reader)
            return 0
        if args.command == "factory-restore-afc-menu-runtime":
            run_factory_restore_afc_menu(reader)
            return 0
        if args.command in {
            "factory-set-afc-runtime",
            "factory-restore-afs-runtime",
        }:
            mode_name = (
                "afc"
                if args.command == "factory-set-afc-runtime"
                else "afs"
            )
            set_command = FACTORY_FOCUS_SET_COMMANDS[mode_name]
            print("operation: USB factory command-65 HblShell focus-mode request")
            print(f"  requested={mode_name}")
            set_output = reader.factory_shell(set_command)
            if set_output:
                print("  set-output:")
                print(set_output)
            read_output = reader.factory_shell(FACTORY_FOCUS_READ_COMMAND)
            print("focus-mode readback:")
            print(read_output or "(empty)")
            expected = (
                "E_FocusModes_Afc(2)"
                if mode_name == "afc"
                else "E_FocusModes_Afs(1)"
            )
            if expected not in read_output:
                raise UsbFactoryError(
                    f"USB factory readback did not show {expected}; "
                    "the runtime request was not verified"
                )
            print("readback=OK; this change is runtime-only")
            return 0
        if args.command == "read-basics":
            parameters = [27, 28]
        elif args.command == "read-focus-mode":
            parameters = [2]
        elif args.command in {
            "set-focus-mode",
            "set-afc-runtime",
            "restore-afs-runtime",
        }:
            if args.command == "set-focus-mode":
                mode_name = args.mode
            elif args.command == "set-afc-runtime":
                mode_name = "afc"
            else:
                mode_name = "afs"
            mode = WRITABLE_FOCUS_MODES[mode_name]
            print("operation: runtime-only USB WriteParameter focus_mode")
            print(f"  requested={mode_name} ({FOCUS_MODE_NAMES[mode]})")
            request = build_write_focus_mode(mode, sequence=1)
            print(f"  request={request.hex(' ')}")
            write_response = reader.write_focus_mode(mode, sequence=1)
            if write_response:
                print(f"  immediate_reply={write_response[:64].hex(' ')}")
                if len(write_response) > 64:
                    print(f"  immediate_reply_truncated={len(write_response)} bytes")
            else:
                print("  immediate_reply=(empty/timeout; readback is authoritative)")
            response = reader.read_parameter(2, sequence=2)
            print("focus-mode readback:")
            print(
                f"  sequence={response.sequence} frame_length={response.frame_length} "
                f"transport_bytes={response.transport_length}"
            )
            print(f"  value: {format_parameter_value(2, response.value)}")
            print(f"  frame[0:{response.frame_length}]: {response.raw_frame.hex(' ')}")
            expected = f"i{mode}".encode("ascii")
            if response.value != expected:
                raise UsbFactoryError(
                    "focus-mode readback mismatch: "
                    f"requested {expected!r}, got {response.value!r}"
                )
            print("  readback=OK; this change is runtime-only")
            return 0
        else:
            parameters = [args.parameter]
        for parameter_id in parameters:
            response = reader.read_parameter(parameter_id)
            print(f"parameter {parameter_id} ({ALLOWED_PARAMETERS[parameter_id]})")
            print(
                f"  sequence={response.sequence} frame_length={response.frame_length} "
                f"transport_bytes={response.transport_length} "
                f"echoed_id={response.echoed_parameter_id}"
            )
            print(f"  value: {format_parameter_value(parameter_id, response.value)}")
            print(f"  frame[0:{response.frame_length}]: {response.raw_frame.hex(' ')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UsbFactoryError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
