"""Run the actual C preference code against temporary files, without a camera."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src/speed-buff-server.c'
HARNESS = r'''
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static const char *path;
static int short_write, sync_failure;
char *test_getenv(const char *name) { return 0; }
int test_open(const char *name, int flags, ...) {
 if(strcmp(name,"/blackbox/.x2d-play-software/free-notice-seen")) exit(50);
 int native = flags & 1 ? O_WRONLY : O_RDONLY;
 if(flags & 64) native |= O_CREAT;
 if(flags & 128) native |= O_EXCL;
 if(flags & 131072) native |= O_NOFOLLOW;
 if(flags & 2048) native |= O_NONBLOCK;
 return open(path,native,0600);
}
long test_read(int fd,void *value,unsigned long n) { return read(fd,value,n); }
long test_write(int fd,const void *value,unsigned long n) { return write(fd,value,short_write ? n-1 : n); }
int test_close(int fd) { return close(fd); }
int test_fsync(int fd) { return sync_failure ? -1 : fsync(fd); }
int test_unlink(const char *name) {
 if(strcmp(name,"/blackbox/.x2d-play-software/free-notice-seen")) exit(51);
 return unlink(path);
}
extern int probe_seen(void),probe_ack(void);
int main(int argc,char **argv) {
 if(argc!=3) return 52;
 path=argv[1];short_write=!strcmp(argv[2],"short");sync_failure=!strcmp(argv[2],"syncfail");
 printf("%d\n",!strcmp(argv[2],"read") ? probe_seen() : probe_ack());
 return 0;
}
'''


class FreeNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='free-notice-')
        cls.root = Path(cls.folder.name)
        names = ('getenv', 'open', 'read', 'write', 'close', 'fsync', 'unlink')
        source = ''.join('#define ' + name + ' test_' + name + '\n' for name in names)
        source += SOURCE.read_text()
        source += '\nint probe_seen(void){return notice_seen();}\nint probe_ack(void){return notice_ack();}\n'
        (cls.root / 'server.c').write_text(source)
        (cls.root / 'harness.c').write_text(HARNESS)
        cls.binary = cls.root / 'probe'
        compiler = ['/usr/bin/clang']
        if sys.platform == 'darwin':
            native = subprocess.run(['/usr/bin/arch', '-arm64'] + compiler + ['--version'], capture_output=True, text=True)
            if native.returncode == 0: compiler = ['/usr/bin/arch', '-arm64'] + compiler
        result = subprocess.run(compiler + ['-fno-builtin', str(cls.root / 'server.c'),
                                 str(cls.root / 'harness.c'), '-o', str(cls.binary)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def probe(self, path, action):
        result = subprocess.run([str(self.binary), str(path), action], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        return int(result.stdout.strip())

    def test_ack_survives_a_fresh_process_and_repeated_ack(self):
        path = self.root / 'valid'
        self.assertEqual(self.probe(path, 'read'), 0)
        self.assertFalse(path.exists())
        self.assertEqual(self.probe(path, 'ack'), 0)
        self.assertEqual(path.read_bytes(), b'1\n')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.probe(path, 'read'), 1)
        stamp = path.stat().st_mtime_ns
        self.assertEqual(self.probe(path, 'ack'), 0)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_foreign_files_and_symlinks_are_never_overwritten_or_accepted(self):
        for index, value in enumerate((b'', b'1', b'1\nextra', b'foreign')):
            path = self.root / ('foreign-' + str(index))
            path.write_bytes(value)
            self.assertEqual(self.probe(path, 'read'), 0)
            self.assertEqual(self.probe(path, 'ack'), -1)
            self.assertEqual(path.read_bytes(), value)
        target = self.root / 'symlink-target'
        target.write_bytes(b'1\n')
        link = self.root / 'symlink'
        link.symlink_to(target)
        self.assertEqual(self.probe(link, 'read'), 0)
        self.assertEqual(self.probe(link, 'ack'), -1)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), b'1\n')

    def test_short_write_and_sync_failure_leave_no_false_ack(self):
        for failure in ('short', 'syncfail'):
            path = self.root / failure
            self.assertEqual(self.probe(path, failure), -1)
            self.assertFalse(path.exists())
            self.assertEqual(self.probe(path, 'read'), 0)
            self.assertEqual(self.probe(path, 'ack'), 0)

    def test_unavailable_parent_and_fifo_do_not_block_or_create_ack(self):
        path = self.root / 'missing-parent' / 'seen'
        self.assertEqual(self.probe(path, 'read'), 0)
        self.assertEqual(self.probe(path, 'ack'), -1)
        fifo = self.root / 'fifo'
        __import__('os').mkfifo(fifo, 0o600)
        self.assertEqual(self.probe(fifo, 'read'), 0)
        self.assertEqual(self.probe(fifo, 'ack'), -1)


if __name__ == '__main__':
    unittest.main()
