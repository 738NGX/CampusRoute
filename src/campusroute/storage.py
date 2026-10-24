import json
import os
from pathlib import Path
import tempfile


def write_json(path: Path, value):
    content = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.stem + '-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
