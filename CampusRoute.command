#!/bin/zsh
set -uo pipefail

task_root=${0:A:h}
cd "$task_root"
mkdir -p "$task_root/work/.cache"
task_temporary=$(mktemp -d "$task_root/work/.cache/launch.XXXXXXXX") || exit 1
trap 'rm -rf -- "$task_temporary"' EXIT
export TMPDIR="$task_temporary"
export PYTHONDONTWRITEBYTECODE=1
task_python="$task_root/.conda/campusroute/bin/python"

if [[ ! -x "$task_python" ]]; then
    print '首次运行需要准备独立的 Miniconda 环境。'
    print '1  开始安装'
    print '0  退出'
    read -r 'task_reply?请选择数字并按回车：'
    if [[ "$task_reply" != '1' ]]; then
        exit 0
    fi
    if ! command -v conda >/dev/null 2>&1; then
        print '未找到 Miniconda。请先按照 README 安装 Miniconda，并在 Terminal 中启用 conda。'
        read -r 'task_reply?按回车关闭窗口。'
        exit 1
    fi
    if ! conda env create --prefix "$task_root/.conda/campusroute" --file environment.yml; then
        print '环境准备失败。请查看窗口中的错误信息，并按照 README 排查后重新安装。'
        read -r 'task_reply?按回车关闭窗口。'
        exit 1
    fi
fi

print '在家里我们就练起来'
if /usr/bin/caffeinate -is "$task_python" -B -m campusroute --root "$task_root"; then
    exit 0
else
    task_status=$?
    read -r 'task_reply?按回车关闭窗口。'
    exit "$task_status"
fi
