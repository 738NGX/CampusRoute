# 开发指南

[返回首页](../README.md)

## 安装与验证

使用 Python 3.11 或更新版本，在项目文件夹执行：

```sh
mkdir -p work/.cache/tmp
```

将当前终端的 `TMPDIR`（Windows 为 `TEMP`、`TMP`）设置为项目内 `work/.cache/tmp`，然后执行：

```sh
python -m pip install -e '.[dev,ios]'
python -m unittest discover -s tests -v
python -m ruff check src tools tests
python tools/check_source.py
python -m pip check
node --check src/campusroute/web/editor.js
python -m build
python -m twine check dist/*
python tools/check_distribution.py
```

仅开发 Android 后端时使用 `.[dev]`。Android APK 构建见 [Android 说明](android.md#构建-apk)。

## 持续集成

GitHub Actions 在推送、Pull Request 与手动运行时验证：

- macOS／Windows 的 Python 3.11、3.12、3.13、3.14、3.15，共10组检查。
- 源码规范、全部测试、依赖完整性、JavaScript 语法及对应平台启动器。
- Python wheel／源码发行包的构建、元数据、资源与本地文件隔离。
- Android 调试 APK 构建与签名校验。

共12项检查，构建产物保留7天，可以在 [Actions](https://github.com/ArtemisJLV/CampusRoute/actions/workflows/test.yml) 下载。自动检查使用真实文件、进程及本地网络；手机授权、驱动、位置显示与断线清理需要结合真实设备验证。

## 文件位置

程序位于 `src/campusroute/`，地图资源位于其 `data/` 与 `web/` 目录，Android 接收应用位于 `android/`，检查与构建工具位于 `tools/`，测试位于 `tests/`。

用户设置、路线收藏、环境、构建结果与临时文件保持在版本库之外。提交前请检查差异，避免加入设备标识、私人路径、密钥或会话数据。
