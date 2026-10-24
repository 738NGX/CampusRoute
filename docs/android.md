# Android 使用说明

## 设备要求

- Windows 10/11 64 位，Python 最低要求为3.11；版本验证范围见 [README](../README.md#python-版本与平台支持)。
- Android 10 或更新版本，能够授权 USB 调试和模拟位置信息应用。
- 支持数据传输的数据线，以及 Android SDK Platform-Tools。Windows 可能需要手机厂商提供的 USB 驱动。
- 构建 APK 需要 JDK 17 或更新版本，以及 Android SDK 平台35和 Build-Tools 35.0.0。

不同厂商的权限与后台管理行为存在差异，目标应用自行决定是否采用 Android 模拟位置。

## 安装与连接

1. 安装 [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)，将 `adb` 加入 PATH。也可以解压到项目内 `work/android-sdk/platform-tools/`。
2. 手机开启 USB 调试，连接电脑、解锁并允许调试。`adb devices -l` 应显示 `device`。
3. 双击 `CampusRoute.cmd`。首次启动自动创建 `.venv` 并安装依赖。指定 Python 使用 `./CampusRoute.ps1 -Python 'Python完整路径'`，升级或修复使用 `./CampusRoute.ps1 -Upgrade`。
4. 选择菜单10，安装 `build/android/CampusRoute-debug.apk`，或者输入自行构建的 APK 路径。保持手机解锁并确认安装。
5. 使用菜单7选择路线、菜单8设置配速与距离、菜单1连接手机。在手机开发者选项中选择 CampusRoute 为模拟位置信息应用，允许定位权限，再点击“启动接收”。
6. 电脑显示起点准备完成后，选择2开始、3暂停、4中止、5恢复定位、0退出。

每次连接都需要在手机确认启动接收。手机应用与前台通知提供“停止并恢复”按钮。

ADB 查找顺序为启动参数 `-Adb`、项目内 Platform-Tools、PATH、`ANDROID_HOME` 和 `ANDROID_SDK_ROOT`。指定完整路径的示例：

```powershell
./CampusRoute.ps1 -Adb 'C:\Android\platform-tools\adb.exe'
```

## 构建 APK

Android Studio 可以打开 `android/` 工程构建。也可以使用已经安装的 JDK 与 Android SDK：

```powershell
python tools/build_android.py --sdk 'Android SDK路径' --java-home 'JDK路径'
```

脚本使用 `platforms;android-35` 与 `build-tools;35.0.0`，输出 `build/android/CampusRoute-debug.apk`，并验证 APK 签名。

本地调试密钥位于 `build/android/debug.keystore`，保留后可覆盖安装后续构建。不同构建环境使用不同调试密钥，签名不同时需要卸载旧 APK 并重新授权。GitHub Actions 的 APK 用于调试验证。

## 路线与设置

菜单7列出内置路线和本地收藏，使用数字选择。地图完成绘制或导入 GPX／GeoJSON 后，默认加入收藏；菜单12可关闭自动保存，地图也可以针对当前路线取消保存。临时路线仅在当前窗口提供编号。

菜单11设置配速与横向波动，默认关闭。暂停、中止及到达目标时保持位置并发送零速度。累计里程按原路线前进距离计算。

## 通信与恢复定位

电脑通过 USB 上的 ADB 转发连接手机本地服务。指令包含会话与递增编号，每条指令都需确认；超过3秒未收到有效回执时结束当前连接并返回菜单。

断线、连续5秒未收到完整指令或服务正常停止时，手机尝试移除测试位置提供器。手机系统强制结束进程或撤销权限可能影响清理；恢复结果未确认时，使用手机“停止并恢复”，必要时重启手机。

“手机已确认坐标”表示定位接口调用及回执校验完成。目标应用的地图显示、位置来源和距离计算需要在目标应用中验证。

## 常见问题

| 现象 | 处理方法 |
| --- | --- |
| 找不到手机 | 检查数据线、USB 驱动、手机解锁与 USB 调试授权 |
| `unauthorized`／`offline` | 重新连接，并在手机确认电脑调试权限 |
| 安装取消或拒绝 | 保持解锁并确认安装；也可将 APK 复制到手机手动安装 |
| 无法准备起点 | 检查系统定位、定位权限和模拟位置应用选择 |
| 回执超时或编号无效 | 查看终端错误，先在手机停止并恢复，再从菜单1重新连接 |
| 锁屏或切换应用后断线 | 检查 CampusRoute 的后台运行及电池管理权限 |
| 目标应用仍显示真实位置 | 检查目标应用的位置权限与刷新行为，分别验证其定位来源 |

错误诊断只显示在当前终端。路线收藏位于 `user-routes/routes.geojson`，使用设置位于 `work/settings.json`；程序不写入运行日志。

## 开发验证

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m ruff check src tools tests
python tools/check_source.py
python -m pip check
```

自动检查覆盖文件读写、菜单进程、回环网络通信和路线计算。手机授权、持续移动、暂停恢复、断线清理、锁屏与目标应用显示需要真实设备验证。
