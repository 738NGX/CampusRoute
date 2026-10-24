# 你跑不过我你信不信 🏃

> **在家里我们就练起来**

把操场装进数字菜单：选择路线、设置配速、准备起点，然后用几个数字控制一段旅程。

软件名称：**CampusRoute** · 平台：**macOS + iPhone** · 代码许可：**GPL-3.0-or-later**

**📦 [下载最新版本](https://github.com/ArtemisJLV/CampusRoute/releases/latest)** · [查看版本更新记录](https://github.com/ArtemisJLV/CampusRoute/releases)

## 先认识一下这位选手

- 🏟️ 上海四所985高校、六个校区的操场预设，附地图与数据来源。
- 🎨 路线可以自己绘制，也可以导入 GPX／GeoJSON。
- ⏱️ 配速从 **2:00／公里** 起步，慢速没有人为上限，目标距离自行设置。
- 🎛️ 开始、暂停、继续、中止、恢复定位，全部收进一个数字菜单。
- 🫧 运行状态保存在内存中，程序不保存运行日志、状态快照或操作历史。

CampusRoute 使用 iPhone 开发者定位接口播放路线，可用于地图、路线和位置功能的调试。默认目标为5公里，默认配速为2:00／公里。

## 出发前，带上这些

| 装备 | 要求 |
| --- | --- |
| Mac | macOS，已验证 Apple Silicon；Intel Mac 尚未验证 |
| iPhone | iOS 17.4 或更新版本，开启开发者模式 |
| 数据线 | 支持数据传输；手机解锁并信任电脑，Finder 能识别设备 |
| Miniconda | 用于创建独立的 Python 3.13 环境 |
| 网络 | 首次安装依赖、准备开发者镜像和加载地图底图时需要联网 |
| 开发者镜像 | 由 pymobiledevice3 准备，须与手机系统版本兼容；可使用现有 Xcode 安装 |

手机开发者模式入口：**设置 → 隐私与安全性 → 开发者模式**。开启后按照系统提示重启并确认。系统升级可能影响开发者服务兼容性。

## 三步进入控制台

1. 从[最新版本发布页](https://github.com/ArtemisJLV/CampusRoute/releases/latest)的 **Assets** 下载 CampusRoute 压缩包，解压到一个固定文件夹。
2. 双击 **`CampusRoute.command`**，首次选择数字 **`1`** 安装独立环境。
3. 连接并解锁 iPhone，开始选择路线和参数。

终端打开后，会显示：

```text
CampusRoute  |  iPhone 路线调试
在家里我们就练起来
```

偏爱 Terminal 的朋友，也可以进入项目文件夹后执行：

```sh
mkdir -p work/.cache/tmp
export TMPDIR="$PWD/work/.cache/tmp"
conda env create --prefix ./.conda/campusroute --file environment.yml
chmod +x CampusRoute.command
./CampusRoute.command
```

Miniconda 需要已经在 Terminal 中启用。安装完成后，日常只需双击启动文件。环境位于 `.conda/campusroute`；更换项目文件夹位置后需要重新创建环境。

### 安装与修复

每次启动都会检查程序能否导入、项目安装信息是否存在，以及依赖版本和依赖关系是否满足安装声明。需要准备环境时，窗口显示 **`1` 安装／修复环境** 和 **`0` 退出**。

选择1后，首次安装会创建独立环境；已有 Conda 环境会在原位置补齐程序和依赖。安装完成后会再次校验，通过后进入控制台。

下载失败或安装中断时，请根据终端错误检查网络和 Miniconda 配置，再次双击启动文件并选择1继续。也可以进入项目文件夹，在 Terminal 中手动修复已有环境：

```sh
conda env update --prefix ./.conda/campusroute --file environment.yml
```

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
| **0** | 发送恢复真实定位指令，关闭地图服务并退出 |

推荐操作顺序：**`7` 选择路线 → `8` 设置参数 → `1` 准备起点 → `2` 开始移动**。

配速采用 `分钟:秒` 格式，例如 `2:00`、`6:30`、`120:00`。最快2:00，慢速没有人为上限。目标公里数可以输入正数，包括小数。

达到目标距离后，程序保持终点位置，等待选择5或0。路线与参数只在当前窗口内生效；重新打开后使用默认设置。

Ctrl+C、关闭终端窗口和正常终止信号会触发设备清理。断线、强制结束进程或电脑断电时，定位恢复可能无法完成；重新连接后执行菜单1、5，必要时重启手机。

## 今天选择哪个操场？🏟️

| 学校 | 校区 | 操场 |
| --- | --- | --- |
| 同济大学 | 四平路 | **一二九运动场（一·二九田径场）** |
| 同济大学 | 嘉定 | 体育中心田径场 |
| 复旦大学 | 邯郸 | 南区田径场 |
| 上海交通大学 | 闵行 | 胡法光体育场 |
| 华东师范大学 | 中山北路 | 共青场 |
| 华东师范大学 | 闵行 | 东田径场 |

每条预设保留 OpenStreetMap 对象链接、学校场馆资料、获取日期与许可信息。地图和路线统一使用 **WGS84** 坐标。

预设沿 OpenStreetMap 场地外轮廓构建，单圈长度以程序计算结果为准。地图存在测绘与更新误差，播放距离按照 WGS84 椭球距离累计。底图由 OpenStreetMap 提供，页面持续显示署名。

## 路线由你画 🎨

1. 在菜单 **9** 打开地图，选择附近校区，或输入 `纬度,经度` 移动地图中心。
2. 点击 **开始绘制**，按照移动顺序点击地图；可以撤销最后一点或清空重画。
3. 环形路线点击 **闭合路线**；开放路线到达终点后沿原路往返。
4. 填写路线名称，点击 **下载 GeoJSON 路线**。
5. 回到操作窗口，输入 **7 → I**，粘贴下载文件的完整路径。

导入时直接读取原文件，程序不额外保存副本。以后再次使用时，重新导入同一文件即可。编辑内置路线后下载的文件会保留来源与数据许可。

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

程序自身不创建运行日志、状态文件、操作历史或自动路线副本。设备标识、移动进度与参数保存在进程内存中；错误信息直接显示在当前终端。多窗口互斥使用目录锁，不生成锁文件。

运行所需的临时目录位于项目内 `work/.cache/`，退出时清理。主动下载的路线文件由用户保存；Miniconda 环境、设备配对资料和开发者镜像供后续连接使用。

本地地图服务只监听 `127.0.0.1`。程序没有遥测、账号登录和数据上传功能。安装依赖与准备镜像会访问相应项目的服务；底图会向 OpenStreetMap 请求当前区域的瓦片。Terminal、浏览器与操作系统各自管理其历史和缓存。

## 开源接力 🤝

代码采用 **GPL-3.0-or-later**，完整条款见 [LICENSE](LICENSE)。路线数据采用 **ODbL-1.0**，Leaflet 地图组件保留 **BSD-2-Clause** 原许可。

感谢 [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)、[gpxpy](https://github.com/tkrajina/gpxpy)、[GeographicLib](https://github.com/geographiclib/geographiclib-python)、[geojson](https://github.com/jazzband/geojson)、[Leaflet](https://leafletjs.com/) 和 [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)。版本、用途、许可及场馆资料详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

学校名称用于标识公开场馆。使用开发者定位接口时，应遵守目标应用的使用规则；应用自身决定轨迹显示、距离计算与记录有效性。
