'use strict';

const map = L.map('map').setView([31.2815, 121.5065], 17);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
}).addTo(map);
const presetLine = L.polyline([], { color: '#6b8d7c', weight: 6, opacity: 0.8 }).addTo(map);
const customLine = L.polyline([], { color: '#db7443', weight: 4 }).addTo(map);
const pointsLayer = L.layerGroup().addTo(map);
const status = document.getElementById('status');
const selector = document.getElementById('preset');
let routes = [];
let coordinates = [];
let drawing = false;
let provenance = {};

function update(message = '') {
  customLine.setLatLngs(coordinates.map(([lon, lat]) => [lat, lon]));
  pointsLayer.clearLayers();
  coordinates.forEach(([lon, lat], index) => {
    L.circleMarker([lat, lon], { radius: index === 0 ? 6 : 3, color: '#a5502c' }).addTo(pointsLayer);
  });
  const closed = coordinates.length > 2 && coordinates[0][0] === coordinates.at(-1)[0]
    && coordinates[0][1] === coordinates.at(-1)[1];
  status.textContent = message || `已绘制${coordinates.length}个坐标点。${closed ? '闭合路线将循环移动。' : '开放路线将沿原路往返。'}`;
  document.getElementById('draw').textContent = drawing ? '暂停绘制' : '开始绘制';
}

function selectPreset() {
  const route = routes[Number(selector.value)];
  const latlngs = route.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
  presetLine.setLatLngs(latlngs);
  map.fitBounds(presetLine.getBounds(), { padding: [45, 45], maxZoom: 19 });
  const source = document.getElementById('source');
  source.replaceChildren();
  source.append('WGS84 · ');
  if (route.properties.source_url) {
    const link = document.createElement('a');
    link.textContent = '查看数据来源';
    link.href = route.properties.source_url;
    link.target = '_blank';
    link.rel = 'noreferrer';
    source.append(link);
  }
  if (Number.isFinite(route.properties.length_m)) source.append(` 路线约${route.properties.length_m.toFixed(1)}米。`);
  source.append(route.properties.geometry_note || '用户导入的自定义路线。');
}

map.on('click', (event) => {
  if (!drawing) return;
  coordinates.push([Number(event.latlng.lng.toFixed(9)), Number(event.latlng.lat.toFixed(9))]);
  update();
});
tiles.on('tileerror', () => {
  status.textContent = '底图加载失败，请检查网络连接。已有路线仍可查看、编辑和下载。';
});
selector.addEventListener('change', selectPreset);
document.getElementById('draw').addEventListener('click', () => { drawing = !drawing; update(); });
document.getElementById('copy').addEventListener('click', () => {
  const route = routes[Number(selector.value)];
  coordinates = route.geometry.coordinates.map((point) => [...point]);
  provenance = {};
  for (const key of ['source', 'source_url', 'license', 'attribution', 'retrieved_at']) {
    if (route.properties[key]) provenance[key] = route.properties[key];
  }
  document.getElementById('name').value = '自定义操场路线';
  drawing = false;
  update('已复制操场路线。可以撤销末尾坐标，再继续绘制。');
});
document.getElementById('undo').addEventListener('click', () => { coordinates.pop(); update(); });
document.getElementById('clear').addEventListener('click', () => {
  coordinates = []; drawing = false; provenance = {}; update();
});
document.getElementById('close').addEventListener('click', () => {
  const distinct = new Set(coordinates.map((point) => point.join(',')));
  if (distinct.size < 3) { update('闭合路线至少需要三个不同的坐标点。'); return; }
  if (coordinates[0].join(',') !== coordinates.at(-1).join(',')) coordinates.push([...coordinates[0]]);
  drawing = false;
  update();
});
document.getElementById('locate').addEventListener('click', () => {
  const input = document.getElementById('center').value;
  const values = input.split(',').map((value) => value.trim());
  const [lat, lon] = values.map(Number);
  if (values.length !== 2 || values.some((value) => value === '') || !Number.isFinite(lat)
      || !Number.isFinite(lon) || Math.abs(lat) > 85 || Math.abs(lon) > 180) {
    update('请输入有效的 WGS84 纬度,经度；地图显示纬度范围为-85至85。');
    return;
  }
  map.setView([lat, lon], 18);
  update('地图中心已更新。点击“开始绘制”后逐点选择路线。');
});
document.getElementById('download').addEventListener('click', () => {
  const name = document.getElementById('name').value.trim();
  if (coordinates.length < 2 || !name) { update('请填写路线名称，并绘制至少两个不同的坐标点。'); return; }
  if (coordinates.some((point, index) => index > 0 && point.join(',') === coordinates[index - 1].join(','))) {
    update('相邻坐标点不能完全相同，请撤销重复坐标。');
    return;
  }
  const feature = {
    type: 'Feature', properties: { ...provenance, name, coordinate_system: 'WGS84' },
    geometry: { type: 'LineString', coordinates },
  };
  const blob = new Blob([JSON.stringify(feature, null, 2)], { type: 'application/geo+json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'custom-route.geojson';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  update('路线已下载。返回操作窗口，选择7 → I，粘贴下载文件的完整路径。');
});

async function initialize() {
  const response = await fetch('routes.json');
  if (!response.ok) throw new Error('操场路线读取失败。');
  const collection = await response.json();
  routes = collection.features;
  routes.forEach((route, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = route.properties.name;
    selector.append(option);
  });
  const initial = new URLSearchParams(window.location.search).get('route');
  if (initial !== null && /^[0-9]+$/.test(initial) && Number(initial) < routes.length) selector.value = initial;
  selectPreset();
  update('选择操场查看跑道；点击“开始绘制”创建自定义路线。');
}

initialize().catch((error) => {
  status.textContent = error.message;
  document.querySelectorAll('button,select').forEach((element) => { element.disabled = true; });
});
