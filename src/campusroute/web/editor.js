'use strict';

const map = L.map('map').setView([31.2815, 121.5065], 17);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
}).addTo(map);
const presetLine = L.polyline([], { color: '#6b8d7c', weight: 6, opacity: 0.8 }).addTo(map);
const customLine = L.polyline([], { color: '#db7443', weight: 4 }).addTo(map);
const pitchLine = L.polygon([], { color: '#3d78a4', weight: 2, dashArray: '5 5', fillOpacity: 0.08 }).addTo(map);
const pointsLayer = L.layerGroup().addTo(map);
const status = document.getElementById('status');
const selector = document.getElementById('preset');
const method = document.getElementById('method');
const distance = document.getElementById('distance');
const distanceNote = document.getElementById('distance-note');
const dimensions = document.getElementById('track-dimensions');
const download = document.getElementById('download');
let routes = [];
let coordinates = [];
let corners = [];
let drawing = false;
let provenance = {};
let lengthM = 0;
let revision = 0;
let calculating = false;

function sourceProperties(properties) {
  const result = {};
  for (const key of ['source', 'source_url', 'license', 'attribution', 'retrieved_at']) {
    if (properties[key]) result[key] = properties[key];
  }
  return result;
}

function isClosed() {
  return coordinates.length > 2 && coordinates[0][0] === coordinates.at(-1)[0]
    && coordinates[0][1] === coordinates.at(-1)[1];
}

function update(message = '') {
  const pitch = method.value === 'pitch';
  customLine.setLatLngs(coordinates.map(([lon, lat]) => [lat, lon]));
  // Sort only the guide polygon; corner identities stay stable while dragging.
  const center = corners.reduce((sum, point) => [sum[0] + point[0] / corners.length,
    sum[1] + point[1] / corners.length], [0, 0]);
  const ordered = [...corners].sort((a, b) =>
    Math.atan2(a[1] - center[1], a[0] - center[0]) - Math.atan2(b[1] - center[1], b[0] - center[0]));
  pitchLine.setLatLngs(pitch ? ordered.map(([lon, lat]) => [lat, lon]) : []);
  pointsLayer.clearLayers();
  if (pitch) {
    corners.forEach(([lon, lat], index) => {
      const marker = L.marker([lat, lon], {
        draggable: true,
        icon: L.divIcon({ className: 'corner-marker', html: String(index + 1), iconSize: [26, 26], iconAnchor: [13, 13] }),
        title: '足球场角点' + (index + 1) + '，可拖动',
      }).addTo(pointsLayer);
      marker.on('dragend', () => {
        const point = marker.getLatLng();
        corners[index] = [Number(point.lng.toFixed(9)), Number(point.lat.toFixed(9))];
        recalculate();
      });
    });
  } else {
    coordinates.forEach(([lon, lat], index) => {
      L.circleMarker([lat, lon], { radius: index === 0 ? 6 : 3, color: '#a5502c' }).addTo(pointsLayer);
    });
  }
  document.getElementById('pitch-options').hidden = !pitch;
  document.getElementById('close').disabled = pitch || coordinates.length < 3 || calculating;
  document.getElementById('undo').disabled = pitch ? corners.length === 0 : coordinates.length === 0;
  document.getElementById('undo').textContent = pitch ? '撤销最后一个角' : '撤销最后一点';
  document.getElementById('draw').textContent = drawing
    ? (pitch ? '暂停选点' : '暂停绘制')
    : (pitch ? (corners.length === 4 ? '重新选四个角' : '选取足球场四角') : '开始绘制');
  distance.textContent = calculating ? '计算中…' : (lengthM === null ? '暂无法计算' : lengthM.toFixed(1) + ' 米');
  document.getElementById('map-distance-label').textContent = pitch
    ? (corners.length < 4 ? '足球场选点' : '估算跑道 · 单圈')
    : ('橙色轨迹 · ' + (isClosed() ? '单圈' : '单程'));
  document.getElementById('map-distance-value').textContent = pitch && corners.length < 4
    ? corners.length + ' / 4' : distance.textContent;
  distanceNote.textContent = pitch
    ? '规则跑道估算；闭合轨迹显示单圈长度，松开角点后重新计算。'
    : (isClosed() ? 'WGS84 椭球计算，当前显示单圈长度。' : 'WGS84 椭球计算，开放路线显示单程长度。');
  download.disabled = calculating || lengthM === null || lengthM < 10 || coordinates.length < 2;
  if (message) {
    status.textContent = message;
  } else if (pitch) {
    status.textContent = corners.length < 4
      ? '已选择' + corners.length + '/4个角。沿足球场边缘依次点击四个角。'
      : '跑道已生成。蓝色为足球场，橙色为估算轨迹；可拖动角点或调整参数。';
  } else {
    status.textContent = '已绘制' + coordinates.length + '个坐标点。'
      + (isClosed() ? '闭合路线将循环移动。' : '开放路线将沿原路往返。');
  }
}

async function post(path, body) {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '计算失败，请检查本地地图服务。');
  return result;
}

async function recalculate() {
  const current = ++revision;
  const pitch = method.value === 'pitch';
  calculating = false;
  lengthM = 0;
  dimensions.textContent = '';
  if (pitch) {
    coordinates = [];
    provenance = {};
    if (corners.length !== 4) { update(); return; }
  } else if (coordinates.length < 2) {
    update();
    return;
  }
  calculating = true;
  lengthM = null;
  update('正在计算轨迹与总距离……');
  try {
    let result;
    if (pitch) {
      const clearance = document.getElementById('clearance');
      const inset = document.getElementById('inset');
      if (!clearance.checkValidity() || !inset.checkValidity()
          || !Number.isFinite(clearance.valueAsNumber) || !Number.isFinite(inset.valueAsNumber)) {
        throw new Error('请填写有效参数：间距0至30米，弯道内收0至50米。');
      }
      result = await post('generate-track', {
        corners, clearance_m: clearance.valueAsNumber, end_inset_m: inset.valueAsNumber,
      });
    } else {
      result = await post('route-length', { coordinates });
    }
    if (current !== revision) return;
    if (pitch) {
      coordinates = result.geometry.coordinates;
      provenance = result.properties;
      const p = result.properties;
      dimensions.textContent = '拟合足球场 ' + p.field_length_m.toFixed(1) + ' × ' + p.field_width_m.toFixed(1)
        + '米；直道 ' + p.straight_length_m.toFixed(1) + '米；弯道半径 ' + p.bend_radius_m.toFixed(1) + '米。';
    }
    lengthM = pitch ? result.properties.length_m : result.length_m;
    calculating = false;
    update();
  } catch (error) {
    if (current !== revision) return;
    calculating = false;
    lengthM = null;
    update(error.message || '计算失败，请检查本地地图服务。');
  }
}

function selectPreset() {
  const route = routes[Number(selector.value)];
  presetLine.setLatLngs(route.geometry.coordinates.map(([lon, lat]) => [lat, lon]));
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
  if (Number.isFinite(route.properties.length_m)) source.append(' 预设路线约' + route.properties.length_m.toFixed(1) + '米。');
  source.append(route.properties.geometry_note || '用户导入的自定义路线。');
}

map.on('click', (event) => {
  if (!drawing) return;
  const point = [Number(event.latlng.lng.toFixed(9)), Number(event.latlng.lat.toFixed(9))];
  if (method.value === 'pitch') {
    if (corners.length >= 4) return;
    corners.push(point);
    if (corners.length === 4) drawing = false;
  } else {
    coordinates.push(point);
    provenance = sourceProperties(provenance);
  }
  recalculate();
});

tiles.on('tileerror', () => { document.getElementById('tile-warning').hidden = false; });
selector.addEventListener('change', selectPreset);
method.addEventListener('change', () => {
  corners = []; coordinates = []; provenance = {}; drawing = false;
  recalculate();
});
for (const id of ['clearance', 'inset']) document.getElementById(id).addEventListener('input', () => {
  if (method.value === 'pitch') recalculate();
});

document.getElementById('draw').addEventListener('click', () => {
  if (method.value === 'pitch' && corners.length === 4) {
    corners = []; coordinates = []; provenance = {}; drawing = true;
    recalculate();
  } else {
    drawing = !drawing;
    update();
  }
});

document.getElementById('copy').addEventListener('click', () => {
  const route = routes[Number(selector.value)];
  method.value = 'manual';
  corners = [];
  coordinates = route.geometry.coordinates.map((point) => [...point]);
  provenance = sourceProperties(route.properties);
  document.getElementById('name').value = '自定义操场路线';
  drawing = false;
  recalculate();
});

document.getElementById('undo').addEventListener('click', () => {
  if (method.value === 'pitch') {
    corners.pop(); drawing = true;
  } else {
    coordinates.pop();
    provenance = sourceProperties(provenance);
  }
  recalculate();
});
document.getElementById('clear').addEventListener('click', () => {
  coordinates = []; corners = []; drawing = false; provenance = {};
  recalculate();
});
document.getElementById('close').addEventListener('click', () => {
  if (method.value !== 'manual') return;
  if (new Set(coordinates.map((point) => point.join(','))).size < 3) {
    update('闭合路线至少需要三个不同的坐标点。'); return;
  }
  if (!isClosed()) coordinates.push([...coordinates[0]]);
  provenance = sourceProperties(provenance);
  drawing = false;
  recalculate();
});
document.getElementById('locate').addEventListener('click', () => {
  const values = document.getElementById('center').value.split(',').map((value) => value.trim());
  const [lat, lon] = values.map(Number);
  if (values.length !== 2 || values.some((value) => value === '') || !Number.isFinite(lat)
      || !Number.isFinite(lon) || Math.abs(lat) > 85 || Math.abs(lon) > 180) {
    update('请输入有效的 WGS84 纬度,经度；地图显示纬度范围为-85至85。'); return;
  }
  map.setView([lat, lon], 18);
  update('地图中心已更新。选择绘制方式，再开始选点。');
});

download.addEventListener('click', () => {
  const name = document.getElementById('name').value.trim();
  if (calculating || lengthM === null || lengthM < 10) { update('请先完成有效轨迹，总长度至少10米。'); return; }
  if (coordinates.length < 2 || !name) { update('请填写路线名称，并绘制至少两个不同的坐标点。'); return; }
  if (coordinates.some((point, index) => index > 0 && point.join(',') === coordinates[index - 1].join(','))) {
    update('相邻坐标点不能完全相同，请撤销重复坐标。'); return;
  }
  const feature = {
    type: 'Feature', properties: { ...provenance, name, coordinate_system: 'WGS84', length_m: lengthM },
    geometry: { type: 'LineString', coordinates },
  };
  const blob = new Blob([JSON.stringify(feature, null, 2)], { type: 'application/geo+json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = 'custom-route.geojson'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  update('路线已下载。返回操作窗口，选择7 → I，粘贴下载文件的完整路径。');
});

async function initialize() {
  const response = await fetch('routes.json');
  if (!response.ok) throw new Error('操场路线读取失败。');
  routes = (await response.json()).features;
  routes.forEach((route, index) => {
    const option = document.createElement('option');
    option.value = String(index); option.textContent = route.properties.name; selector.append(option);
  });
  const initial = new URLSearchParams(window.location.search).get('route');
  if (initial !== null && /^[0-9]+$/.test(initial) && Number(initial) < routes.length) selector.value = initial;
  selectPreset();
  update('选择“四点足球场”，再点击“选取足球场四角”；也可以切换为逐点绘制。');
}

initialize().catch((error) => {
  status.textContent = error.message;
  document.querySelectorAll('button,select').forEach((element) => { element.disabled = true; });
});
