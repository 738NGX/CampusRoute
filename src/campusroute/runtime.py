import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    pass


@contextmanager
def runtime(root: Path):
    descriptor = os.open(root, os.O_RDONLY)
    try:
        try:
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
                    os.environ.pop('TMPDIR')
                else:
                    os.environ['TMPDIR'] = previous_environment
    finally:
        os.close(descriptor)
