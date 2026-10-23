# 第三方项目与数据

| 项目 | 用途 | 版本 | 原许可 |
| --- | --- | --- | --- |
| [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) | USB 设备识别、开发者服务、定位接口 | 11.36.0 | GPL-3.0-or-later |
| [gpxpy](https://github.com/tkrajina/gpxpy) | GPX 文件解析 | 1.6.2 | Apache-2.0 |
| [GeographicLib for Python](https://github.com/geographiclib/geographiclib-python) | WGS84 椭球距离与路线插值 | 2.1 | MIT |
| [geojson](https://github.com/jazzband/geojson) | GeoJSON 文件读取与校验 | 3.2.0 | BSD-3-Clause |
| [Leaflet](https://leafletjs.com/) | 浏览器交互地图 | 1.9.4 | BSD-2-Clause |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | 校园路线几何与在线底图 | 路线文件中记录数据日期 | ODbL-1.0 |

Python 依赖通过包管理器安装；各发行包保留自身许可。Leaflet 的本地 JavaScript、CSS、图片资源未经修改，许可原文保存在 `LICENSES/Leaflet-BSD-2-Clause.txt` 与组件目录中。项目代码使用 GPL-3.0-or-later；Leaflet 资源与路线数据分别遵循原许可。

## 地图数据

`src/campusroute/data/` 的路线几何源自 OpenStreetMap，由 © OpenStreetMap contributors 提供，按照 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) 发布。许可原文见 `LICENSES/ODbL-1.0.txt`。路线文件中的 `source_url` 指向具体地图对象，`retrieved_at` 记录数据获取日期，`geometry_note` 说明路线几何的构成。

在线底图来自 `https://tile.openstreetmap.org/`。地图署名在页面持续显示，瓦片请求遵循 [OpenStreetMap 瓦片使用政策](https://operations.osmfoundation.org/policies/tiles/)；程序不预取或批量下载瓦片。

## 场馆名称资料

- [同济大学体育部：体育场馆开放方案](https://sports.tongji.edu.cn/info/1049/3133.htm)：四平路一·二九田径场与嘉定校区田径场。
- [复旦大学：四校区体育场馆介绍](https://www.fudan.edu.cn/2020/0923/c24a106433/page.htm)：邯郸校区南区田径场。
- [上海交通大学：胡法光体育场翻新工程验收](https://news.sjtu.edu.cn/jdyw/20221129/177130.html)：闵行校区胡法光体育场。
- [华东师范大学：场馆服务介绍](https://www.ecnu.edu.cn/info/1094/62100.htm)：闵行校区东田径场、中北校区共青场。

学校资料用于核对场馆名称与校区归属。路线数据遵循 OpenStreetMap 的数据许可。
