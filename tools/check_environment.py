import argparse
import importlib
from importlib.metadata import version
from pathlib import Path
import tomllib


def main():
    parser = argparse.ArgumentParser(description='检查当前源码版本与设备后端依赖。')
    parser.add_argument('--backend', choices=('android', 'ios'), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with (root / 'pyproject.toml').open('rb') as handle:
        expected = tomllib.load(handle)['project']['version']
    package = importlib.import_module('campusroute')
    installed = version('campusroute')
    if installed != expected or package.__version__ != expected:
        raise RuntimeError(f'已安装版本 {installed}，当前源码版本 {expected}，请使用启动器的升级／修复入口。')
    importlib.import_module('campusroute.console')
    if args.backend == 'ios':
        importlib.import_module('campusroute.device')
    print(f'CampusRoute {installed} 环境检查通过（{args.backend}）。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
