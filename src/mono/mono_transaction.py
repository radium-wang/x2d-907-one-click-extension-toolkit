"""Source-only CFV 4.2.0 monochrome install/restore state machine.

This module has no USB, shell, mount, reboot or camera access. A future
Shuaqi adapter must implement DurableStore with atomic replacement and
directory fsync for every put/remove. It must call restore through an
independent factory-USB path, never through the experimental camera GUI.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol

STOCK_RC_SHA256 = "2aa2c06efcc2d7fac690f7fe5db324e12f02748fb7d368ee5f726c3d5b24f2a9"
SERVICE_RC = "/system/etc/init/camera-service.rc"
MODULE = "/system/lib64/libcfv_mono.so"
ROOT = "/blackbox/.x2d-play-software/mono"
BACKUP = ROOT + "/stock-camera-service.rc"
STATE = ROOT + "/state.json"
FEATURE = "/blackbox/x2d-play-mono.available"
PREF = "/blackbox/x2d-play-mono.enabled"
SERVICE_LINE = b"service camera-service /system/bin/camera-service\n"
HOOK = (b"    setenv CFV_MONO_FEATURE 1\n"
        b"    setenv LD_PRELOAD /system/lib64/libcfv_mono.so\n")


class TransactionError(RuntimeError):
    pass


class DurableStore(Protocol):
    """Each mutation must be atomic and durable before it returns.

    A successful put needs file fsync, atomic rename and parent-directory
    fsync; remove needs parent-directory fsync. Implementations must reject
    symlinks and non-owned paths. No device implementation is supplied here.
    """
    def read(self, path: str) -> bytes: ...
    def exists(self, path: str) -> bool: ...
    def put(self, path: str, data: bytes) -> None: ...
    def remove(self, path: str) -> None: ...


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_rc(stock: bytes) -> bytes:
    if digest(stock) != STOCK_RC_SHA256 or stock.count(SERVICE_LINE) != 1:
        raise TransactionError("camera-service.rc is not exact CFV 4.2.0 stock")
    if b"LD_PRELOAD" in stock:
        raise TransactionError("unexpected existing preload")
    return stock.replace(SERVICE_LINE, SERVICE_LINE + HOOK, 1)


def _state_bytes(phase: str, module_sha: str, candidate_sha: str) -> bytes:
    return (json.dumps({"schema": 1, "phase": phase,
                        "stock_sha256": STOCK_RC_SHA256,
                        "candidate_sha256": candidate_sha,
                        "module_sha256": module_sha},
                       sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


@dataclass(frozen=True)
class Status:
    phase: str
    enabled: bool
    requires_service_restart: bool


class MonoTransaction:
    def __init__(self, store: DurableStore):
        self.store = store

    def _state(self) -> dict | None:
        if not self.store.exists(STATE):
            return None
        try:
            value = json.loads(self.store.read(STATE))
        except (ValueError, UnicodeError) as exc:
            raise TransactionError("invalid transaction journal") from exc
        if (not isinstance(value, dict) or value.get("schema") != 1 or
            value.get("phase") not in ("PREPARING", "HOOKED", "ACTIVE", "RESTORING") or
            value.get("stock_sha256") != STOCK_RC_SHA256 or
            not all(isinstance(value.get(k), str) and
                    re.fullmatch(r"[0-9a-f]{64}", value[k])
                    for k in ("candidate_sha256", "module_sha256"))):
            raise TransactionError("unrecognized transaction journal")
        return value

    def _verify_owned(self, state: dict) -> bytes:
        if not self.store.exists(BACKUP):
            raise TransactionError("stock startup backup missing")
        stock = self.store.read(BACKUP)
        candidate = candidate_rc(stock)
        if digest(candidate) != state["candidate_sha256"]:
            raise TransactionError("startup journal and backup disagree")
        current = self.store.read(SERVICE_RC)
        if current not in (stock, candidate):
            raise TransactionError("startup config changed outside this transaction")
        if self.store.exists(MODULE) and digest(self.store.read(MODULE)) != state["module_sha256"]:
            raise TransactionError("module changed outside this transaction")
        return stock

    def install(self, module_bytes: bytes, expected_module_sha256: str) -> Status:
        """Prepare a dormant preload; availability is not created here.

        An interrupted install is recovered by a later independent restore()
        call. This does not assert autonomous recovery during a power cut.
        """
        if (not re.fullmatch(r"[0-9a-f]{64}", expected_module_sha256) or
            not module_bytes or digest(module_bytes) != expected_module_sha256):
            raise TransactionError("module does not match reviewed manifest")
        if any(self.store.exists(p) for p in (STATE, BACKUP, MODULE, FEATURE, PREF)):
            raise TransactionError("mono installation already present or incomplete")
        stock = self.store.read(SERVICE_RC)
        candidate = candidate_rc(stock)
        self.store.put(BACKUP, stock)
        self.store.put(STATE, _state_bytes("PREPARING", expected_module_sha256, digest(candidate)))
        self.store.put(MODULE, module_bytes)
        self.store.put(PREF, b"0\n")
        self.store.put(SERVICE_RC, candidate)
        self.store.put(STATE, _state_bytes("HOOKED", expected_module_sha256, digest(candidate)))
        return Status("HOOKED", False, True)

    def activate(self, verify_runtime: Callable[[], bool]) -> Status:
        """Expose the feature only after an independent runtime verifier passes."""
        # Revalidation after a restart must fail closed even if an earlier
        # service instance had already made the feature available.
        if self.store.exists(FEATURE):
            self.store.remove(FEATURE)
        state = self._state()
        if not state or state["phase"] not in ("HOOKED", "ACTIVE"):
            raise TransactionError("mono startup hook is not prepared")
        stock = self._verify_owned(state)
        if self.store.read(SERVICE_RC) != candidate_rc(stock):
            raise TransactionError("mono startup hook is absent")
        if not self.store.exists(MODULE) or not self.store.exists(PREF):
            raise TransactionError("mono module or preference missing")
        if not verify_runtime():
            raise TransactionError("camera-service runtime was not verified")
        self.store.put(STATE, _state_bytes("ACTIVE", state["module_sha256"],
                                           state["candidate_sha256"]))
        self.store.put(FEATURE, b"1\n")
        return Status("ACTIVE", self.is_enabled(), False)

    def is_enabled(self) -> bool:
        """Mirrors the native fail-closed availability/preference contract."""
        return (self.store.exists(FEATURE) and self.store.read(FEATURE) == b"1\n" and
                self.store.exists(PREF) and self.store.read(PREF) == b"1\n")

    def restore(self) -> Status:
        """Idempotent host-side rollback, independent of camera GUI startup.

        Availability is removed first. A camera-service restart remains
        necessary to unload any library mapped in a running process.
        """
        self.store.remove(FEATURE)
        state = self._state()
        if state is None:
            # Power loss after backup but before journal, or during cleanup.
            if self.store.exists(BACKUP):
                if (digest(self.store.read(BACKUP)) != STOCK_RC_SHA256 or
                    digest(self.store.read(SERVICE_RC)) != STOCK_RC_SHA256 or
                    any(self.store.exists(p) for p in (MODULE, PREF))):
                    raise TransactionError("orphan backup cannot be safely discarded")
                self.store.remove(BACKUP)
            if any(self.store.exists(p) for p in (MODULE, PREF)):
                raise TransactionError("mono files exist without a journal")
            if digest(self.store.read(SERVICE_RC)) != STOCK_RC_SHA256:
                raise TransactionError("startup config is not stock")
            return Status("STOCK", False, False)
        stock = self._verify_owned(state)
        self.store.put(STATE, _state_bytes("RESTORING", state["module_sha256"],
                                           state["candidate_sha256"]))
        self.store.remove(PREF)
        if self.store.read(SERVICE_RC) != stock:
            self.store.put(SERVICE_RC, stock)
        self.store.remove(MODULE)
        if digest(self.store.read(SERVICE_RC)) != STOCK_RC_SHA256:
            raise TransactionError("stock startup config not restored")
        self.store.remove(STATE)
        self.store.remove(BACKUP)
        return Status("STOCK", False, True)
