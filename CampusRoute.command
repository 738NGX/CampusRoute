#!/bin/zsh
set -uo pipefail

task_root=${0:A:h}
cd "$task_root" || exit 1
mkdir -p "$task_root/work/.cache"
task_temporary=$(mktemp -d "$task_root/work/.cache/launch.XXXXXXXX") || exit 1
trap 'rm -rf -- "$task_temporary"' EXIT
export TMPDIR="$task_temporary"
export PYTHONDONTWRITEBYTECODE=1
task_prefix="$task_root/.conda/campusroute"
task_python="$task_prefix/bin/python"

task_environment_ready() {
    [[ -x "$task_python" ]] || return 1
    "$task_python" -B -c 'import campusroute.console; import campusroute.device; from importlib.metadata import distribution; distribution("campusroute")' || return 1
    "$task_python" -B -m pip --no-cache-dir --disable-pip-version-check check
}

if ! task_environment_ready >/dev/null 2>&1; then
    print '独立环境尚未准备完成，或程序及依赖不完整。'
    print '1  安装／修复环境'
    print '0  退出'
    read -r 'task_reply?请选择数字并按回车：'
    if [[ "$task_reply" != '1' ]]; then
        exit 0
    fi
    if ! command -v conda >/dev/null 2>&1; then
        print '安装或修复需要 Miniconda。请按照 README 安装，并在 Terminal 中启用 conda。'
        read -r 'task_reply?按回车关闭窗口。'
        exit 1
    fi
    if [[ -d "$task_prefix/conda-meta" ]]; then
        task_action=update
    else
        task_action=create
    fi
    if ! conda env "$task_action" --prefix "$task_prefix" --file "$task_root/environment.yml"; then
        print '安装未完成。请根据上方错误检查网络和 Miniconda 配置，再次打开后选择1继续。'
        read -r 'task_reply?按回车关闭窗口。'
        exit 1
    fi
    "$task_python" -B -m pip install --no-cache-dir -e '.[ios]' || exit 1
    if ! task_environment_ready; then
        print '环境校验未通过。请根据上方错误完成处理，再次打开后选择1继续。'
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
