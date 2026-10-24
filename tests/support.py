import os
from pathlib import Path
import subprocess
import sys

CACHE = Path(__file__).resolve().parents[1] / 'work' / '.cache'


def run_console(root: Path, commands, backend='android'):
    environment = dict(os.environ)
    environment.update(TMPDIR=str(root), TEMP=str(root), TMP=str(root),
                       PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    return subprocess.run(
        [sys.executable, '-B', '-m', 'campusroute', '--backend', backend, '--root', str(root)],
        input=commands, text=True, encoding='utf-8', capture_output=True,
        timeout=30, env=environment,
    )
