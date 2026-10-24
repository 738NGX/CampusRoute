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
    if version('campusroute') != expected or package.__version__ != expected:
        raise RuntimeError(f'当前源码要求 CampusRoute {expected}，请安装或修复环境。')
    importlib.import_module('campusroute.console')
    if args.backend == 'ios':
        importlib.import_module('campusroute.device')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
