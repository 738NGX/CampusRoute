import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    pass


class _WindowsDirectoryLock:
    def __init__(self, root: Path):
        self.path = root / 'work' / '.campusroute.lock'
        self.handle = None

    def acquire(self):
        import msvcrt

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a+b')
        try:
            if self.handle.seek(0, os.SEEK_END) == 0:
                self.handle.write(b'\0')
                self.handle.flush()
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.handle.close()
            self.handle = None
            raise BlockingIOError from None

    def release(self):
        if self.handle is None:
            return
        import msvcrt

        try:
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close()
            self.handle = None


@contextmanager
def runtime(root: Path):
    windows_lock = None
    descriptor = None
    try:
        try:
            if os.name == 'nt':
                windows_lock = _WindowsDirectoryLock(root)
                windows_lock.acquire()
            else:
                import fcntl

                descriptor = os.open(root, os.O_RDONLY)
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunningError('操作窗口已经打开，请使用现有窗口。') from None
        cache = root / 'work' / '.cache'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='run-', dir=cache) as directory:
            previous_directory = tempfile.tempdir
            previous_environment = os.environ.get('TMPDIR')
            tempfile.tempdir = directory
            os.environ['TMPDIR'] = directory
            try:
                yield
            finally:
                tempfile.tempdir = previous_directory
                if previous_environment is None:
                    os.environ.pop('TMPDIR', None)
                else:
                    os.environ['TMPDIR'] = previous_environment
    finally:
        if windows_lock is not None:
            windows_lock.release()
        if descriptor is not None:
            os.close(descriptor)
