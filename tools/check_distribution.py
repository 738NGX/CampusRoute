import argparse
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {'work', 'user-routes', '.conda', '.venv', '.vscode', '.git', '__pycache__'}


def main():
    parser = argparse.ArgumentParser(description='检查 Python 发行包的入口、资源和本地文件隔离。')
    parser.add_argument('directory', nargs='?', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    wheels = list(args.directory.glob('*.whl'))
    sources = list(args.directory.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError('需要一个 wheel 和一个源码发行包。')
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        for required in ('campusroute/console.py', 'campusroute/library.py', 'campusroute/web/editor.js',
                         'campusroute/data/tongji-siping.geojson'):
            if required not in names:
                raise ValueError(f'wheel 缺少资源：{required}')
    with tarfile.open(sources[0], 'r:gz') as archive:
        source_names = archive.getnames()
        members = {name.split('/', 1)[1] for name in source_names if '/' in name}
        for required in ('CampusRoute.command', 'CampusRoute.cmd', 'CampusRoute.bat', 'CampusRoute.ps1',
                         'tools/check_environment.py', 'README.md', 'LICENSE'):
            if required not in members:
                raise ValueError(f'源码发行包缺少文件：{required}')
        names.extend(source_names)
    for name in names:
        path = Path(name)
        if PRIVATE_PARTS.intersection(path.parts) or path.suffix in ('.log', '.pyc', '.keystore'):
            raise ValueError(f'发行包包含本地文件：{name}')
    print('发行包入口、资源与本地文件隔离检查通过。')


if __name__ == '__main__':
    main()
