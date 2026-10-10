"""Factory-USB adapter for an optional, dormant Shuaqi monochrome module.

Importing this file has no device effect. The caller supplies Shuaqi's verified
USB transport. X2D and CFV have separate target gates and must have separate
runtime evidence; a result on one is never inferred for the other.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from typing import Protocol

from mono_transaction import BACKUP, FEATURE, MODULE, PREF, ROOT, SERVICE_RC, STATE
from mono_transaction import STOCK_RC_SHA256, candidate_rc

STAGE = "/blackbox/.x2d-play-software/stage"
RC_NEXT = "/system/etc/init/.camera-service.rc.cfv-mono.next"
MODULE_NEXT = "/system/lib64/.libcfv_mono.so.next"
MODELS = frozenset(("X2D 100C", "907X & CFV 100C"))


class MonoUsbError(RuntimeError):
    pass


class Transport(Protocol):
    def verify_target(self) -> None: ...
    def camera_model(self) -> str: ...
    def shell(self, command: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
    def ensure_adb(self) -> None: ...
    def upload(self, name: str, data: bytes) -> None: ...
    def validate_script(self, script: str) -> None: ...


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


PROBE_EXPORTS = frozenset(("duss_hal_ienc_encfrm", "duss_hal_heifenc_encfrm"))


def probe_exports(data: bytes) -> set[str]:
    """Read defined ELF64 dynamic symbols without binutils or dependencies."""
    if len(data) < 64:
        raise MonoUsbError("truncated module")
    shoff = struct.unpack_from("<Q", data, 40)[0]
    shentsize, shnum = struct.unpack_from("<HH", data, 58)
    if shentsize < 64 or not 1 <= shnum <= 2048 or shoff > len(data) or shoff + shentsize * shnum > len(data):
        raise MonoUsbError("invalid ELF section table")

    def section(index):
        base = shoff + index * shentsize
        typ = struct.unpack_from("<I", data, base + 4)[0]
        off, size = struct.unpack_from("<QQ", data, base + 24)
        link = struct.unpack_from("<I", data, base + 40)[0]
        entsize = struct.unpack_from("<Q", data, base + 56)[0]
        if off > len(data) or size > len(data) - off:
            raise MonoUsbError("ELF section outside module")
        return typ, off, size, link, entsize

    names = set()
    for index in range(shnum):
        typ, off, size, link, entsize = section(index)
        if typ != 11:
            continue
        if link >= shnum or entsize < 24 or size % entsize:
            raise MonoUsbError("invalid ELF dynamic symbol table")
        string_type, string_off, string_size, _, _ = section(link)
        if string_type != 3:
            raise MonoUsbError("ELF dynamic string table missing")
        strings = data[string_off:string_off + string_size]
        for cursor in range(off, off + size, entsize):
            name_offset = struct.unpack_from("<I", data, cursor)[0]
            section_index = struct.unpack_from("<H", data, cursor + 6)[0]
            if section_index == 0 or name_offset >= len(strings):
                continue
            end = strings.find(b"\0", name_offset)
            if end < 0:
                raise MonoUsbError("unterminated ELF symbol")
            try:
                names.add(strings[name_offset:end].decode("ascii"))
            except UnicodeError:
                raise MonoUsbError("invalid ELF symbol") from None
    return names


def verify_module(data: bytes, expected_sha: str) -> None:
    if not re.fullmatch("[0-9a-f]{64}", expected_sha) or sha(data) != expected_sha:
        raise MonoUsbError("module hash differs from reviewed package")
    # ELF64 little-endian, ET_DYN, EM_AARCH64. This is only an identity check.
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or data[16:20] != b"\x03\x00\xb7\x00":
        raise MonoUsbError("module is not an AArch64 shared object")
    if not PROBE_EXPORTS <= probe_exports(data):
        raise MonoUsbError("required observation-only HAL exports are absent")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    if phnum:
        if phentsize < 56 or phoff > len(data) or phoff + phentsize * phnum > len(data):
            raise MonoUsbError("invalid ELF program headers")
        for index in range(phnum):
            base = phoff + index * phentsize
            segment_type, flags = struct.unpack_from("<II", data, base)
            if segment_type == 1 and flags & 3 == 3:
                raise MonoUsbError("module has writable executable segment")



def journal(phase: str, module_sha: str, candidate_sha: str) -> bytes:
    return (json.dumps(dict(schema=1, phase=phase,
                            stock_sha256=STOCK_RC_SHA256,
                            module_sha256=module_sha,
                            candidate_sha256=candidate_sha),
                       sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def parse_journal(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise MonoUsbError("invalid monochrome journal") from exc
    if not isinstance(value, dict) or value.get("schema") != 1 or value.get("phase") not in (
        "PREPARING", "HOOKED", "ACTIVE", "RESTORING"
    ) or value.get("stock_sha256") != STOCK_RC_SHA256:
        raise MonoUsbError("unknown monochrome journal")
    for key in ("module_sha256", "candidate_sha256"):
        if not isinstance(value.get(key), str) or not re.fullmatch("[0-9a-f]{64}", value[key]):
            raise MonoUsbError("invalid monochrome journal checksum")
    return value


def _header() -> str:
    return """#!/system/bin/sh
set -eu
export PATH=/system/bin:/system/xbin:/sbin TMPDIR=/tmp
hashok() { [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]; }
state() { awk '$2=="/system"{print $1,$3,$4}' /proc/mounts; }
original_mount=$(state)
case "$original_mount" in '/dev/block/mmcblk0p16 ext4 ro,'*|'/dev/block/mmcblk0p17 ext4 ro,'*) ;; *) exit 30;; esac
"""


def install_script(module_sha: str, candidate_sha: str) -> str:
    for value in (module_sha, candidate_sha):
        if not re.fullmatch("[0-9a-f]{64}", value):
            raise MonoUsbError("invalid install checksum")
    preparing = journal("PREPARING", module_sha, candidate_sha).decode().strip()
    hooked = journal("HOOKED", module_sha, candidate_sha).decode().strip()
    return _header() + f"""
hashok {SERVICE_RC} {STOCK_RC_SHA256}
hashok {STAGE}/monostock {STOCK_RC_SHA256}
hashok {STAGE}/monorc {candidate_sha}
hashok {STAGE}/monomod {module_sha}
[ ! -L {ROOT} ] && [ ! -L {SERVICE_RC} ] && [ ! -L {MODULE} ] && [ ! -L {RC_NEXT} ] && [ ! -L {MODULE_NEXT} ]
[ ! -e {ROOT} ] && [ ! -e {MODULE} ] && [ ! -e {FEATURE} ] && [ ! -e {PREF} ] && [ ! -e {RC_NEXT} ] && [ ! -e {MODULE_NEXT} ]
mkdir -p {ROOT}
chmod 700 {ROOT}
cp {STAGE}/monostock {BACKUP}
hashok {BACKUP} {STOCK_RC_SHA256}
printf '%s\\n' '{preparing}' >{STATE}.next
sync
mv {STATE}.next {STATE}
sync
trap 'mount -o remount,ro /system' EXIT
mount -o remount,rw /system
cp {STAGE}/monomod /system/lib64/.libcfv_mono.so.next
hashok /system/lib64/.libcfv_mono.so.next {module_sha}
chmod 0644 /system/lib64/.libcfv_mono.so.next
mv /system/lib64/.libcfv_mono.so.next {MODULE}
hashok {MODULE} {module_sha}
printf '0\\n' >{PREF}.next
sync
mv {PREF}.next {PREF}
sync
cp {STAGE}/monorc /system/etc/init/.camera-service.rc.cfv-mono.next
hashok /system/etc/init/.camera-service.rc.cfv-mono.next {candidate_sha}
chmod 0644 /system/etc/init/.camera-service.rc.cfv-mono.next
mv /system/etc/init/.camera-service.rc.cfv-mono.next {SERVICE_RC}
hashok {SERVICE_RC} {candidate_sha}
sync
mount -o remount,ro /system
[ "$(state)" = "$original_mount" ]
printf '%s\\n' '{hooked}' >{STATE}.next
sync
mv {STATE}.next {STATE}
sync
echo MONO_PREPARED
"""


def restore_script(module_sha: str, candidate_sha: str, current_sha: str,
                   module_present: bool) -> str:
    for value in (module_sha, candidate_sha, current_sha):
        if not re.fullmatch("[0-9a-f]{64}", value):
            raise MonoUsbError("invalid restore checksum")
    if current_sha not in (STOCK_RC_SHA256, candidate_sha):
        raise MonoUsbError("startup config changed outside monochrome transaction")
    module_guard = f"hashok {MODULE} {module_sha}" if module_present else f"[ ! -e {MODULE} ]"
    restoring = journal("RESTORING", module_sha, candidate_sha).decode().strip()
    return _header() + f"""
[ ! -L {ROOT} ] && [ ! -L {SERVICE_RC} ] && [ ! -L {MODULE} ] && [ ! -L {RC_NEXT} ] && [ ! -L {MODULE_NEXT} ]
hashok {BACKUP} {STOCK_RC_SHA256}
hashok {SERVICE_RC} {current_sha}
{module_guard}
rm -f {FEATURE} {FEATURE}.next
printf '%s\\n' '{restoring}' >{STATE}.next
sync
mv {STATE}.next {STATE}
sync
trap 'mount -o remount,ro /system' EXIT
mount -o remount,rw /system
cp {BACKUP} /system/etc/init/.camera-service.rc.cfv-mono.next
hashok /system/etc/init/.camera-service.rc.cfv-mono.next {STOCK_RC_SHA256}
chmod 0644 /system/etc/init/.camera-service.rc.cfv-mono.next
mv /system/etc/init/.camera-service.rc.cfv-mono.next {SERVICE_RC}
hashok {SERVICE_RC} {STOCK_RC_SHA256}
rm -f {MODULE} /system/lib64/.libcfv_mono.so.next
sync
mount -o remount,ro /system
[ "$(state)" = "$original_mount" ]
rm -f {PREF} {PREF}.next
sync
rm -f {STATE}.next {STATE}
sync
rm -f {BACKUP}
rmdir {ROOT}
echo MONO_RESTORED
"""


def orphan_cleanup_script(has_backup: bool) -> str:
    """Undo a cut after mkdir/backup but before the first durable journal."""
    backup_guard = (f"hashok {BACKUP} {STOCK_RC_SHA256}" if has_backup
                    else f"[ ! -e {BACKUP} ]")
    return _header() + f"""
[ ! -L {ROOT} ] && [ ! -L {BACKUP} ] && [ ! -L {STATE}.next ]
hashok {SERVICE_RC} {STOCK_RC_SHA256}
[ ! -e {MODULE} ] && [ ! -e {FEATURE} ] && [ ! -e {PREF} ]
[ ! -e {STATE} ]
{backup_guard}
rm -f {BACKUP} {STATE}.next
rmdir {ROOT}
sync
echo MONO_ORPHAN_CLEANED
"""


@dataclass
class MonoUsbAdapter:
    transport: Transport
    expected_model: str

    def __post_init__(self):
        if self.expected_model not in MODELS:
            raise MonoUsbError("unknown camera model gate")

    def _check_target(self):
        self.transport.verify_target()
        if self.transport.camera_model() != self.expected_model:
            raise MonoUsbError("camera model differs from monochrome target")

    def _safe_paths(self) -> None:
        for path in (ROOT, BACKUP, STATE, STATE + ".next", MODULE, MODULE_NEXT,
                     FEATURE, FEATURE + ".next", PREF, PREF + ".next", SERVICE_RC, RC_NEXT):
            if self.transport.shell(f"test ! -L {path} && echo SAFE || echo NO") != "SAFE":
                raise MonoUsbError("symlink at monochrome owned path")

    def _exists(self, path: str) -> bool:
        if path not in (ROOT, BACKUP, STATE, MODULE, FEATURE, PREF):
            raise MonoUsbError("unowned monochrome path")
        return self.transport.shell(f"test -e {path} && echo YES || echo NO") == "YES"

    def install(self, module: bytes, expected_sha: str) -> str:
        verify_module(module, expected_sha)
        self._check_target()
        self._safe_paths()
        if any(self._exists(p) for p in (ROOT, MODULE, FEATURE, PREF)):
            raise MonoUsbError("existing monochrome state; restore before install")
        stock = self.transport.read_bytes(SERVICE_RC)
        candidate = candidate_rc(stock)
        candidate_sha = sha(candidate)
        script = install_script(expected_sha, candidate_sha)
        self.transport.validate_script(script)
        self.transport.ensure_adb()
        if self.transport.shell(f"test ! -L {STAGE} && mkdir -p {STAGE} && chmod 700 {STAGE} && echo SAFE") != "SAFE":
            raise MonoUsbError("unsafe upload stage")
        for name, data in (("monostock", stock), ("monorc", candidate),
                           ("monomod", module), ("monoinstall", script.encode())):
            self.transport.upload(name, data)
        if self.transport.shell(f"sh {STAGE}/monoinstall") != "MONO_PREPARED":
            raise MonoUsbError("installation not confirmed; independent restore required")
        if sha(self.transport.read_bytes(SERVICE_RC)) != candidate_sha or not self._exists(STATE):
            raise MonoUsbError("installation readback failed; independent restore required")
        # The feature marker remains absent and the preference is zero.
        return "HOOKED_DISABLED_RESTART_REQUIRED"

    def restore(self) -> str:
        self._check_target()
        self._safe_paths()
        if not self._exists(STATE):
            if any(self._exists(p) for p in (MODULE, FEATURE, PREF)):
                raise MonoUsbError("orphan monochrome files require review")
            if sha(self.transport.read_bytes(SERVICE_RC)) != STOCK_RC_SHA256:
                raise MonoUsbError("startup config is not stock and has no journal")
            if self._exists(ROOT):
                has_backup = self._exists(BACKUP)
                if has_backup and sha(self.transport.read_bytes(BACKUP)) != STOCK_RC_SHA256:
                    raise MonoUsbError("orphan stock backup changed")
                script = orphan_cleanup_script(has_backup)
                self.transport.validate_script(script)
                self.transport.ensure_adb()
                if self.transport.shell(f"test ! -L {STAGE} && mkdir -p {STAGE} && chmod 700 {STAGE} && echo SAFE") != "SAFE":
                    raise MonoUsbError("unsafe recovery stage")
                self.transport.upload("monoorphan", script.encode())
                if self.transport.shell(f"sh {STAGE}/monoorphan") != "MONO_ORPHAN_CLEANED":
                    raise MonoUsbError("orphan cleanup not confirmed")
                if self._exists(ROOT):
                    raise MonoUsbError("orphan cleanup readback failed")
                return "STOCK_ORPHAN_CLEANED"
            return "ALREADY_STOCK"
        state = parse_journal(self.transport.read_bytes(STATE))
        stock = self.transport.read_bytes(BACKUP)
        candidate = candidate_rc(stock)
        if sha(candidate) != state["candidate_sha256"]:
            raise MonoUsbError("backup and journal disagree")
        current = self.transport.read_bytes(SERVICE_RC)
        module_present = self._exists(MODULE)
        if module_present and self.transport.shell(f"sha256sum {MODULE}").split()[0] != state["module_sha256"]:
            raise MonoUsbError("module changed outside monochrome transaction")
        script = restore_script(state["module_sha256"], state["candidate_sha256"],
                                sha(current), module_present)
        self.transport.validate_script(script)
        self.transport.ensure_adb()
        if self.transport.shell(f"test ! -L {STAGE} && mkdir -p {STAGE} && chmod 700 {STAGE} && echo SAFE") != "SAFE":
            raise MonoUsbError("unsafe recovery stage")
        self.transport.upload("monorestore", script.encode())
        if self.transport.shell(f"sh {STAGE}/monorestore") != "MONO_RESTORED":
            raise MonoUsbError("independent restore not confirmed")
        if sha(self.transport.read_bytes(SERVICE_RC)) != STOCK_RC_SHA256 or any(
            self._exists(p) for p in (ROOT, MODULE, FEATURE, PREF)
        ):
            raise MonoUsbError("restore readback failed")
        return "STOCK_RESTART_REQUIRED"
