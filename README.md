# 你跑不过我你信不信 🏃

> **在家里我们就练起来**

把操场装进数字菜单：选择路线、设置配速、准备起点，然后用几个数字控制一段旅程。

软件名称：**CampusRoute** · 平台：**macOS + iPhone／Windows + iPhone／Windows + Android** · 代码许可：**GPL-3.0-or-later**

**📦 [下载最新版本](https://github.com/ArtemisJLV/CampusRoute/releases/latest)** · [查看版本更新记录](https://github.com/ArtemisJLV/CampusRoute/releases)

## 先认识一下这位选手

- 🏟️ 上海五所高校、七个校区的操场预设，附地图与来源说明；上财武东路线为用户四点生成的估算轨迹。
- 🎨 路线可以自己绘制，也可以导入 GPX／GeoJSON。
- ⏱️ 配速从 **2:00／公里** 起步，慢速没有人为上限，目标距离自行设置。
- 🎛️ 开始、暂停、继续、中止、恢复定位，全部收进一个数字菜单。
- 💾 自动收藏自定义路线并分配数字编号，记住路线、配速和目标距离；运行进度保存在内存中。

CampusRoute 使用 Android 标准模拟位置接口或 iPhone 开发者定位接口播放路线，可用于地图、路线和位置功能的调试。默认目标为5公里，默认配速为2:00／公里。

## Windows + Android 开始使用

Windows 支持 Python **3.11—3.13**，Android 配套 APK 最低支持 Android 10。Android 稳定性尚待完整真机验收，兼容性与验收项目见 [Android说明](docs/android.md)。

1. 准备 Python 3.11—3.13 和 Android SDK Platform-Tools，确保 `adb` 在 PATH 中；手机开启 USB 调试，解锁后允许电脑调试。
2. 双击 **`CampusRoute.cmd`**，创建或使用项目内 `.venv` 环境。需要指定解释器时，在 PowerShell 中执行 `./CampusRoute.ps1 -Python 'Python完整路径'`。
3. 选择菜单 **10** 安装 `build/android/CampusRoute-debug.apk`。源码没有预置APK时，先按下方说明构建。
4. **7 → 选择路线，8 → 设置参数，1 → 连接手机**。连接时会打开手机端；在开发者选项中选择 CampusRoute 为模拟位置应用，允许定位权限并点击 **启动接收**。
5. 电脑选择 **2** 开始移动，**5** 恢复定位，**0** 退出。手机应用及通知也提供 **停止并恢复**。

APK可以使用Android Studio打开 `android/` 构建，也可以在已安装JDK、Android SDK平台35及Build-Tools 35.0.0后执行：

```powershell
python tools/build_android.py --sdk 'Android SDK路径' --java-home 'JDK路径'
```

需要指定ADB时使用 `./CampusRoute.ps1 -Adb 'adb.exe完整路径'`；升级或修复环境使用 `-Upgrade`。也可从 [Google 官方页面](https://developer.android.com/tools/releases/platform-tools)下载 Platform-Tools，解压为项目内 `work/android-sdk/platform-tools/`；程序优先使用此处的ADB，其次查找 PATH 与 Android SDK 环境变量，显式 `-Adb` 始终优先。Android 模式安装通用依赖；iPhone 模式另外安装 `ios` 可选依赖。完整构建步骤与故障处理见 [Android说明](docs/android.md)。

Android位置更新通过USB上的持续连接传输并要求回执。断线或连续5秒未收到完整指令后，手机尝试移除模拟位置。系统强制结束、厂商电池管理及定位权限变化仍需实机验证。Android模拟位置带有系统标记，目标应用是否使用这些位置由其自身实现决定。

## iPhone 所需环境（macOS／Windows）

| 装备 | 要求 |
| --- | --- |
| 电脑 | macOS（已验证 Apple Silicon；Intel Mac 尚未验证）或 Windows 10/11 64 位 |
| iPhone | iOS 17.4 或更新版本，开启开发者模式 |
| 数据线 | 支持数据传输；手机解锁并信任电脑。macOS 用 Finder 识别，Windows 需安装 Apple 设备支持（iTunes 或“Apple 设备”应用） |
| Python 环境 | macOS 使用 Miniconda 创建独立 Python 3.11 环境；Windows 使用 Python 3.11—3.13，启动器会创建 `.venv` |
| 网络 | 首次安装依赖、准备开发者镜像和加载地图底图时需要联网 |
| 开发者镜像 | 由 pymobiledevice3 准备，须与手机系统版本兼容；macOS 可使用现有 Xcode 安装 |

手机开发者模式入口：**设置 → 隐私与安全性 → 开发者模式**。开启后按照系统提示重启并确认。系统升级可能影响开发者服务兼容性。

## iPhone 三步进入控制台

1. 从[最新版本发布页](https://github.com/ArtemisJLV/CampusRoute/releases/latest)的 **Assets** 下载 CampusRoute 压缩包，解压到一个固定文件夹。
2. macOS 双击 **`CampusRoute.command`**，需要准备环境时选择数字 **`1`**；Windows 双击 **`CampusRoute.bat`**，启动器会安装或更新 iPhone 依赖。Windows 的 **`CampusRoute.cmd`** 用于 Android。
3. 连接并解锁 iPhone，开始选择路线和参数。

终端打开后，会显示：

```text
CampusRoute  |  iPhone 路线调试
在家里我们就练起来
```

macOS 也可以进入项目文件夹后执行：

```sh
mkdir -p work/.cache/tmp
export TMPDIR="$PWD/work/.cache/tmp"
conda env create --prefix ./.conda/campusroute --file environment.yml
conda run --prefix ./.conda/campusroute python -m pip install --no-cache-dir -e '.[ios]'
chmod +x CampusRoute.command
./CampusRoute.command
```

Miniconda 需要已经在 Terminal 中启用。安装完成后，日常只需双击启动文件。macOS 环境位于 `.conda/campusroute`；Windows 环境位于 `.venv`。更换项目文件夹位置后需要重新创建环境。

Windows 也可以在 PowerShell 中指定 iPhone 后端与 Python 路径：

```powershell
./CampusRoute.ps1 -Backend ios -Python 'Python完整路径'
```

Windows 手动安装 iPhone 依赖：

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[ios]"
.venv\Scripts\python -m campusroute --root . --backend ios
```

### 安装与修复

启动器同时核对已安装发行包版本、程序版本和当前源码版本，并检查所选设备后端的依赖。版本不一致时，macOS 显示 **`1` 安装／升级／修复环境** 和 **`0` 退出**；Windows 自动更新独立环境，检查通过后才会启动程序。

macOS 首次安装会创建独立 Conda 环境；已有环境会在原位置补齐程序和依赖。Windows 使用 Python 3.11—3.13 创建 `.venv`，根据所选后端安装当前项目。安装完成后会再次校验，通过后进入控制台。

下载失败或安装中断时，请根据终端错误检查网络和 Python 环境，再次双击启动文件并选择1继续。macOS 也可以进入项目文件夹，在 Terminal 中手动修复已有环境：

```sh
conda env update --prefix ./.conda/campusroute --file environment.yml
conda run --prefix ./.conda/campusroute python -m pip install --no-cache-dir -e '.[ios]'
```

主动升级或修复当前源码对应的环境：

```sh
./CampusRoute.command --upgrade
```

Windows 使用 `./CampusRoute.ps1 -Backend ios -Upgrade` 升级 iPhone 环境；Android 环境使用 `./CampusRoute.ps1 -Upgrade`。`--repair`／`-Repair` 同样可用。升级入口安装本地项目文件夹内的版本；更新源码可重新下载压缩包或手动拉取 GitHub。

## 数字遥控器 🎛️

| 按键 | 会发生什么 |
| --- | --- |
| **1** | 识别 USB 手机并准备起点；多台设备时提示选择 |
| **2** | 开始移动，或者从暂停位置继续 |
| **3** | 暂停移动，持续保持当前位置 |
| **4** | 中止本次移动，持续保持当前位置 |
| **5** | 发送恢复真实定位指令，关闭设备连接 |
| **6** | 刷新累计距离、移动用时和当前状态 |
| **7** | 选择内置路线；输入 `I` 导入自己的路线 |
| **8** | 设置配速与目标公里数 |
| **9** | 打开操场地图，绘制自己的路线 |
| **10** | Android后端：安装或更新配套APK |
| **11** | 开关及设置配速波动、轨迹横向偏移 |
| **12** | 设置自定义路线是否默认保存为本地收藏 |
| **0** | 发送恢复真实定位指令，关闭地图服务并退出 |

推荐操作顺序：**`7` 选择路线 → `8` 设置参数 → `1` 准备起点 → `2` 开始移动**。

配速采用 `分钟:秒` 格式，例如 `2:00`、`6:30`、`120:00`。最快2:00，慢速没有人为上限。目标公里数可以输入正数，包括小数。

菜单 **11** 可开启配速与轨迹波动，默认关闭。输入 `1` 开启，依次设置配速波动百分比（0—20）和最大横向偏移米数（0—3），回车采用初始值 **±5%、0.6米**；输入 `2` 关闭并保留上次幅度。幅度输入时 `0` 表示禁用该项，`Q` 取消。修改前需先用菜单5断开，下次连接生效，开关与幅度自动保存。

开启后，配速与偏移会以十几秒到数分钟的周期缓慢变化，每次新连接重新生成变化曲线，起点从零偏移逐渐进入波动。以6:00配速、±5%为例，配速限制在5:42—6:18之间；最快仍不超过2:00／公里，因此2:00附近的波动会被截断。横向偏移以原路线为中心，不知道实际跑道边界，建议先用0.6米等小幅度。目标和累计距离仍按原路线的前进里程计算，横向偏移可能使地图统计的实际轨迹长度略有不同。

暂停、中止、到达目标时，偏移与位置一起冻结，速度为零；继续移动时接着暂停前的变化播放。关闭波动后沿用原有匀速轨迹。

连接后，控制台约每秒原地刷新状态、累计距离、移动用时、手机已确认坐标及已发送速度／朝向，无需反复输入6。暂停或中止会在最后确认的位置立即发送零速度定位，收到回执后才显示成功，之后持续保持该点；暂停后距离与用时保持不变。刷新只在收到位置回执后进行。重定向到文件时不输出动态刷新控制符。

Android 回执超时或无效时，结束本次会话，显示错误和清理结果后返回菜单，保留路线、配速和目标距离。按手机提示停止并恢复后可用菜单1重新连接，新连接等待用户开始移动。

达到目标距离后，程序保持终点位置，等待选择5或0。路线选择、配速、目标距离、波动与保存开关写入项目内 `work/settings.json`，下次启动自动恢复；连接状态和移动进度每次重新开始。首次启动使用默认设置。设置文件损坏时停止启动并显示错误，检查或删除该文件后可以重新设置。

Ctrl+C和可处理的正常终止信号会触发设备清理。关闭窗口、强制结束进程或断电可能无法执行电脑端清理。Android接收端会在断线或超时后尝试移除模拟位置；也可点击手机端停止按钮。iPhone可重新连接后执行菜单1、5，必要时重启手机。

## 今天选择哪个操场？🏟️

| 学校 | 校区 | 操场 |
| --- | --- | --- |
| 同济大学 | 四平路 | **一二九运动场（一·二九田径场）** |
| 同济大学 | 嘉定 | 体育中心田径场 |
| 复旦大学 | 邯郸 | 南区田径场 |
| 上海交通大学 | 闵行 | 胡法光体育场 |
| 华东师范大学 | 中山北路 | 共青场 |
| 华东师范大学 | 闵行 | 东田径场 |
| 上海财经大学 | 武东路 | 田径场 |

**上海财经大学 · 武东路校区 · 田径场** 已加入第7条预设，来源为用户提供的 `custom-route.geojson`。路线包含209个点，以足球场四角、2米最小间距、10米弯道内收生成闭合轨迹，保留四角、参数和估算标记；未将它标为实测跑道或标准400米。数据位于 `src/campusroute/data/sufe-wudong.geojson`。

OSM预设保留地图对象链接、学校场馆资料、获取日期与许可信息；用户提供的估算路线保留原文件名、接收日期及生成参数。地图和路线统一使用 **WGS84** 坐标。

原有六条预设沿 OpenStreetMap 场地外轮廓构建，上财预设由用户四角选点后参数化生成；单圈长度以程序计算结果为准。地图存在测绘与更新误差，估算轨迹亦可能偏离实际跑道。播放距离按照 WGS84 椭球距离累计。底图由 OpenStreetMap 提供，页面持续显示署名。

## 路线由你画 🎨

1. 在菜单 **9** 打开地图，选择附近校区，或输入 `纬度,经度` 移动地图中心。
2. 默认选择 **四点足球场 → 自动生成跑道**，点击 **选取足球场四角**，沿球场边缘点选四个角；程序自动生成闭合跑道。
3. 拖动蓝色角点可修正位置；调整 **最小间距** 和 **弯道内收** 可改变跑道大小。也可切换为 **逐点绘制路线**；手动画环形路线时点击 **闭合路线**。
4. 填写路线名称，点击 **完成路线**。默认勾选保存，页面会显示新路线编号；需要文件副本时另行点击 **下载 GeoJSON 副本**。
5. 回到操作窗口，输入 **7 → 对应编号**。保存的路线在下次启动仍然可选；也可以使用 **7 → I** 导入已有 GPX／GeoJSON 文件。

绘制完成和导入的路线默认加入 `user-routes/routes.geojson`，内置路线之后按保存顺序分配数字编号。重复保存相同路线会复用已有选项，切换路线保留全部收藏，原导入文件移动或删除不影响使用。编辑内置路线时保留来源与数据许可。

地图取消勾选 **保存为路线选项，供下次使用**，该路线仅在本次窗口提供编号。终端菜单 **12 → 2** 可以关闭后续导入和地图的默认保存，**12 → 1** 重新开启；已经打开的地图页面需要重新加载以采用新的默认值。关闭保存开关会保留现有收藏。手动下载的 GeoJSON 文件由用户管理。

地图右上角与侧栏实时显示当前轨迹总距离，闭合路线为单圈长度，开放路线为单程长度。四点选择、角点拖动、参数调整和手动编辑后会重新计算，距离与播放模块同样采用 WGS84 椭球计算。

四点生成采用“矩形足球场 + 两条直道 + 两段半圆”的估算模型。最小间距为足球场边界到跑道的最近距离；弯道内收为两端半圆圆心相对球门线向场内移动的距离，默认分别为2米和10米。它不能唯一还原真实跑道，也不强制凑成400米；下载文件会保留四角、生成参数和估算标记。例如105×68米球场在默认参数下生成的单圈约405米。使用前请结合实际场地检查。

### 已经有路线文件

| 文件 | 接口要求 |
| --- | --- |
| `.gpx` | 包含一条连续的 track segment 或 route |
| `.geojson` | 一个 `Feature`，几何为 `LineString`，坐标格式为 `[经度, 纬度]` |

路线至少10米，相邻坐标不能重复。GPX 的时间与海拔不参与播放，移动速度由菜单配速决定。

GeoJSON 示例：

```json
{
  "type": "Feature",
  "properties": {"name": "我的路线", "coordinate_system": "WGS84"},
  "geometry": {
    "type": "LineString",
    "coordinates": [[121.4992, 31.2821], [121.4998, 31.2817]]
  }
}
```

高德 GCJ-02、百度 BD-09 坐标需要先转换为 WGS84。程序根据 `properties.coordinate_system` 校验声明，无法自动识别未标注坐标的来源。

## 关于本地记录 🫧

程序在 `work/settings.json` 保存路线选择、配速、目标距离、波动与保存开关，在 `user-routes/routes.geojson` 保存收藏路线的坐标和来源。关闭自动保存后，临时路线留在当前窗口内存中，不写入设置文件。删除设置文件恢复默认参数；删除路线收藏前，请先切换到内置路线。两个目录都不提交到版本库。设备标识、移动进度和会话令牌只保存在进程内存中；程序不保存运行日志或操作历史，错误信息直接显示在当前终端。macOS使用目录锁，Windows使用命名互斥量，不生成锁文件。Android接收端的会话和坐标保存在内存中，不自动恢复或重播旧轨迹。

运行所需的临时目录位于项目内 `work/.cache/`，正常退出时清理本次运行子目录。主动下载的路线文件由用户保存；Python环境、Android构建产物和调试密钥、Apple设备配对资料和开发者镜像供后续使用。ADB和操作系统自行管理其缓存和记录。

本地地图服务只监听 `127.0.0.1`。程序没有遥测、账号登录和数据上传功能。安装依赖与准备镜像会访问相应项目的服务；底图会向 OpenStreetMap 请求当前区域的瓦片。Terminal、浏览器与操作系统各自管理其历史和缓存。

## 开源接力 🤝

代码采用 **GPL-3.0-or-later**，完整条款见 [LICENSE](LICENSE)。路线数据采用 **ODbL-1.0**，Leaflet 地图组件保留 **BSD-2-Clause** 原许可。

感谢 [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)、[gpxpy](https://github.com/tkrajina/gpxpy)、[GeographicLib](https://github.com/geographiclib/geographiclib-python)、[geojson](https://github.com/jazzband/geojson)、[Leaflet](https://leafletjs.com/) 和 [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)。版本、用途、许可及场馆资料详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

学校名称用于标识公开场馆。使用开发者定位接口时，应遵守目标应用的使用规则；应用自身决定轨迹显示、距离计算与记录有效性。

## 一起开发 🔧

```sh
python -m pip install -e '.[dev,ios]'
python -m unittest discover -s tests -v
python -m ruff check src tools tests
python tools/check_source.py
python -m build
python -m twine check dist/*
python tools/check_distribution.py
```

GitHub Actions 在推送、Pull Request 和手动运行时检查 Windows／macOS 的 Python 3.11—3.13、源码规范、全部测试、依赖、JavaScript 语法、发行包与 Android APK 构建。构建产物保留7天，可在 Actions 页面下载；正式版本下载见 Releases。
