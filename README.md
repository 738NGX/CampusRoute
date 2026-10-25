# 你跑不过我你信不信 🏃

> **在家里我们就练起来**

**CampusRoute** 是一个手机路线与定位调试工具。用 USB 连接手机，选择路线、设置配速，再用终端里的数字菜单控制模拟移动。

**[📦 下载最新版本](https://github.com/ArtemisJLV/CampusRoute/releases/latest)** · [📖 使用手册](docs/usage.md) · [💬 反馈问题](https://github.com/ArtemisJLV/CampusRoute/issues)

## 这位选手有什么本领？

- 🏟️ **操场已经备好**：上海五所高校、七个校区的路线预设。
- 🎨 **路线自己做主**：地图绘制、足球场四点生成跑道，也能导入 GPX／GeoJSON；自定义路线默认收藏并获得数字编号。
- ⏱️ **节奏自己决定**：配速最快 **2:00／公里**，慢速没有人为上限，目标距离自由设置。
- 🎛️ **几个数字就能控制**：开始、暂停、继续、中止、恢复定位；可选配速波动与横向偏移。
- 💾 **记得你的偏好**：保留路线与参数，程序不保存运行日志和操作历史。

## 开始之前

| 你的电脑和手机 | 需要准备 |
| --- | --- |
| **macOS + iPhone** | Miniconda、iOS **17.4+**、支持数据传输的 USB 线 |
| **Windows + iPhone** | Windows **10/11 64位**、Python、Apple 设备支持、iOS **17.4+**、USB 线 |
| **Windows + Android** | Windows **10/11 64位**、Python、[ADB](https://developer.android.com/tools/releases/platform-tools)、Android **10+**、USB 线 |

Python 最低要求为 **3.11（`>=3.11`）**；**3.11、3.12、3.13、3.14、3.15** 已通过 Windows／macOS 的 [CI 验证](https://github.com/ArtemisJLV/CampusRoute/actions/workflows/test.yml)。首次安装依赖、准备 iPhone 开发者镜像和加载地图需要联网。

macOS + iPhone 已在 Apple Silicon Mac 上完成手机操作验证。Intel Mac、Windows + iPhone 和 Windows + Android 的完整真机兼容性仍需验证；CI 检查覆盖程序与启动流程。

## 三步，让手机上场 🔌

### 1. 下载并解压

打开[发布页](https://github.com/ArtemisJLV/CampusRoute/releases/latest)，下载 **`CampusRoute-v版本号.zip`**，完整解压到固定文件夹。

### 2. 双击对应启动文件

| 使用组合 | 双击这个文件 | 首次启动 |
| --- | --- | --- |
| macOS + iPhone | **`CampusRoute.command`** | 选择 **`1`** 安装环境；Miniconda 需已在 Terminal 中启用 |
| Windows + iPhone | **`CampusRoute.bat`** | 自动创建环境并安装依赖 |
| Windows + Android | **`CampusRoute.cmd`** | 自动创建环境；进入菜单后先输入 **`10`** 安装配套 APK |

iPhone：开启 **设置 → 隐私与安全性 → 开发者模式**，连接电脑、解锁并信任。macOS 的 Finder 或 Windows 的“Apple 设备”应用应能识别手机。

Android：开启 **USB 调试**，连接后允许电脑调试。配套 APK 位于完整下载包的 `build/android/CampusRoute-debug.apk`；后续连接时，按手机提示选择模拟位置应用、允许定位权限并点击 **启动接收**。

安装遇到问题，查看 [iPhone 安装说明](docs/iphone.md) 或 [Android 安装说明](docs/android.md)。

### 3. 输入数字，开始移动

按顺序逐个输入数字，每次按回车：

```text
7  选择路线
8  设置配速与目标距离，例如 6:00、2.5 公里
1  连接手机，准备路线起点
2  开始移动 🏃
```

| 接下来想做什么？ | 输入数字 |
| --- | --- |
| 暂停／继续 | **`3`**／**`2`** |
| 中止本次移动，保持当前位置 | **`4`** |
| 恢复真实定位，断开手机 | **`5`** |
| 恢复真实定位并退出 | **`0`** |

达到目标距离后会保持终点，选择 **`5`** 或 **`0`** 恢复定位。修改路线和参数前，也需要先选择 **`5`**。

## 想换个操场，或者自己画？🎨

内置路线：同济四平路 **一二九运动场**、同济嘉定、复旦邯郸、上海交大闵行、华东师大中山北路／闵行、上海财大武东路。路线为地图轮廓或四点生成的估算轨迹，单圈长度以程序计算结果为准。

输入 **`9`** 打开地图 → 绘制路线或选取足球场四角 → 填写名称并点击 **完成路线** → 回到终端，输入 **`7`** 按新编号选择。默认保存，下次打开仍然可用；取消地图中的保存勾选可仅供本次使用。

已有文件？输入 **`7 → I`** 导入 GPX／GeoJSON。坐标需要使用 **WGS84**。完整说明见 [自定义路线](docs/usage.md#自定义路线)。

## 更多玩法与说明

- [使用手册](docs/usage.md)：完整菜单、路线收藏、波动参数、数据保存与常见问题。
- [iPhone 安装说明](docs/iphone.md)／[Android 安装说明](docs/android.md)：环境准备、升级、修复与 APK 构建。
- [开发指南](docs/development.md)：源码安装、测试与构建；每个版本的变化见 [Releases](https://github.com/ArtemisJLV/CampusRoute/releases)。

设置与路线收藏保存在本地，程序没有遥测和数据上传功能；地图底图使用 OpenStreetMap。设备和目标应用自行决定定位显示及距离统计，使用时请遵守相应应用的规则。[本地数据说明](docs/usage.md#本地数据与隐私)

## 开源接力，感谢队友 🤝

- [@738NGX](https://github.com/738NGX)：Windows／Android 支持、配套应用、路线生成、距离显示、参数保存与运动波动（[PR #1](https://github.com/ArtemisJLV/CampusRoute/pull/1)）。
- [@windfall-gif](https://github.com/windfall-gif)：Windows + iPhone 支持与开发者镜像准备（[PR #2](https://github.com/ArtemisJLV/CampusRoute/pull/2)）。

感谢 pymobiledevice3、gpxpy、GeographicLib、geojson、Leaflet 和 OpenStreetMap contributors。项目来源、依赖许可及地图署名见 [第三方声明](THIRD_PARTY_NOTICES.md)。

代码采用 [GPL-3.0-or-later](LICENSE)，路线数据采用 [ODbL-1.0](LICENSES/ODbL-1.0.txt)，Leaflet 保留 [BSD-2-Clause](LICENSES/Leaflet-BSD-2-Clause.txt) 许可。
