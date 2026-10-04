"""Own only this app's read-only update check and private ADB server processes."""
import ctypes as C
import socket
import subprocess
import tempfile
import threading
import time


def stop_process(child):
    if child.poll() is None:
        try: child.terminate()
        except OSError:
            if child.poll() is None: raise
        try: child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=2)
    else:
        child.wait()


class UpdateCheck:
    """Serialize cancellation with launch, including a worker not yet started."""
    def __init__(self):
        self.lock = threading.Lock()
        self.closed = False
        self.child = None

    def launch(self, args, **options):
        with self.lock:
            if self.closed: return None
            self.child = subprocess.Popen(args, **options)
            return self.child

    def release(self, child):
        with self.lock:
            if self.child is child: self.child = None

    def close(self):
        with self.lock:
            self.closed = True
            child, self.child = self.child, None
        if child is not None: stop_process(child)


class BasicLimits(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64),
                ('flags', C.c_uint32), ('minimum', C.c_size_t), ('maximum', C.c_size_t),
                ('active', C.c_uint32), ('affinity', C.c_size_t),
                ('priority', C.c_uint32), ('scheduling', C.c_uint32)]


class ExtendedLimits(C.Structure):
    _fields_ = [('basic', BasicLimits), ('io', C.c_uint64 * 6),
                ('process_memory', C.c_size_t), ('job_memory', C.c_size_t),
                ('peak_process_memory', C.c_size_t), ('peak_job_memory', C.c_size_t)]


class ProcessJob:
    """Windows also releases the private server if its owner crashes."""
    def __init__(self):
        kernel = C.WinDLL('kernel32', use_last_error=True)
        def api(name, result, *args):
            fn = getattr(kernel, name); fn.restype = result; fn.argtypes = list(args)
            return fn
        create = api('CreateJobObjectW', C.c_void_p, C.c_void_p, C.c_wchar_p)
        configure = api('SetInformationJobObject', C.c_int, C.c_void_p, C.c_int, C.c_void_p, C.c_uint32)
        self.assign = api('AssignProcessToJobObject', C.c_int, C.c_void_p, C.c_void_p)
        self.close_handle = api('CloseHandle', C.c_int, C.c_void_p)
        self.handle = create(None, None)  # Unnamed, non-inheritable, never a shared system job.
        if not self.handle: raise OSError('无法创建 ADB 进程退出保护；相机安装尚未开始')
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not configure(self.handle, 9, C.byref(limits), C.sizeof(limits)):
            self.close()
            raise OSError('无法设置 ADB 进程退出保护；相机安装尚未开始')

    def attach(self, child):
        if not self.assign(self.handle, int(child._handle)):
            raise OSError('无法管理 ADB 进程；相机安装尚未开始')

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            self.close_handle(handle)


def server_ready(endpoint):
    """Query the host socket directly; never auto-start another ADB daemon."""
    host, port = endpoint[4:].rsplit(':', 1)
    # ADB's localhost listener is IPv4 loopback. Probe it directly, without DNS.
    if host == 'localhost': host = '127.0.0.1'
    with socket.create_connection((host, int(port)), timeout=.25) as connection:
        connection.sendall(b'000chost:version')
        reply = b''
        while len(reply) < 4:
            block = connection.recv(4-len(reply))
            if not block: return False
            reply += block
        return reply == b'OKAY'


class ADBSession:
    def __init__(self, executable, job_factory=ProcessJob):
        self.executable = executable
        self.job_factory = job_factory
        self.job = self.child = self.output = None
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            # ADB accepts localhost (or an omitted host) for a loopback listener;
            # a numeric 127.0.0.1 host is rejected as an unsupported listen host.
            self.endpoint = 'tcp:localhost:' + str(reservation.getsockname()[1])

    def prefix(self):
        return [self.executable, '-L', self.endpoint]

    def start(self, emit, diagnose):
        if self.child is not None and self.child.poll() is None: return
        try:
            self.job = self.job_factory()
            self.output = tempfile.TemporaryFile()
            self.child = subprocess.Popen(self.prefix() + ['server', 'nodaemon'],
                stdin=subprocess.DEVNULL, stdout=self.output, stderr=self.output,
                creationflags=0x08000000, close_fds=True)
            self.job.attach(self.child)
            deadline, notice = time.monotonic()+90, time.monotonic()
            while True:
                code = self.child.poll()
                if code is not None:
                    self.output.seek(0, 2)
                    self.output.seek(max(0, self.output.tell()-65536))
                    raise RuntimeError(diagnose(code, self.output.read().decode('utf-8', errors='replace')))
                try:
                    if server_ready(self.endpoint): return
                except OSError: pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('等待 ADB 启动超时（90 秒），请完成 Windows 的提示并检查是否有其他 ADB 程序或安全软件拦截，再重试；相机安装尚未开始')
                if time.monotonic()-notice >= 5:
                    emit('progress', message='正在等待 ADB 完成启动，请处理 Windows 提示；相机安装尚未开始', percent=10)
                    notice = time.monotonic()
                time.sleep(.25)
        except Exception:
            self.close()
            raise

    def close(self):
        try:
            if self.child is not None: stop_process(self.child)
        finally:
            self.child = None
            if self.job is not None: self.job.close(); self.job = None
            if self.output is not None: self.output.close(); self.output = None
