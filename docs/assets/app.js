'use strict';

// 杵築市中心座標
const KITSUKI_CENTER = [33.416, 131.621];
const INITIAL_ZOOM = 12;

let map;
let pondLayers = {};
let selectedPondId = null;
let pondData = {};  // id -> pond オブジェクト

async function init() {
  map = L.map('map').setView(KITSUKI_CENTER, INITIAL_ZOOM);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  try {
    const resp = await fetch('data.json');
    if (!resp.ok) throw new Error(`data.json の読み込みに失敗: ${resp.status}`);
    const data = await resp.json();
    renderData(data);
  } catch (e) {
    console.error(e);
    document.getElementById('no-selection').textContent =
      'データの読み込みに失敗しました。data.json を確認してください。';
  }
}

function renderData(data) {
  // 更新日時を表示
  if (data.updated_at) {
    document.getElementById('updated-at').textContent =
      `最終更新: ${data.updated_at.replace('T', ' ')} UTC`;
  }

  data.ponds.forEach(pond => {
    pondData[pond.id] = pond;
  });

  // GEEアセットのポリゴンは data.json に含めないため、
  // 池のマーカー（最新面積に応じた円）を地図上に描画する
  // ※GeoJSON境界データが別途提供された場合はここで L.geoJSON() を使用
  data.ponds.forEach(pond => {
    if (!pond.timeseries || pond.timeseries.length === 0) return;

    const latest = pond.timeseries[pond.timeseries.length - 1];
    const radius = Math.max(30, Math.sqrt(latest.water_area_m2) * 0.5);

    const circle = L.circle(KITSUKI_CENTER, {
      radius: 10,   // 後でGeoJSONで上書き予定
      color: '#1565c0',
      fillColor: '#42a5f5',
      fillOpacity: 0.6,
      weight: 1.5,
    });

    // 池ごとに色分け（面積の大小で濃淡）
    const layer = L.circleMarker(KITSUKI_CENTER, {
      radius: 8,
      color: '#1565c0',
      fillColor: '#42a5f5',
      fillOpacity: 0.7,
      weight: 1,
    });

    layer.on('click', () => selectPond(pond.id));
    layer.bindTooltip(`${pond.name}（${pond.region}）`, { permanent: false });

    pondLayers[pond.id] = layer;
  });

  // GeoJSON ポリゴンデータがある場合はここで描画
  // fetchGeoJsonAndRender(data);

  showNoSelection();
}

function selectPond(pondId) {
  // 選択解除
  if (selectedPondId && pondLayers[selectedPondId]) {
    pondLayers[selectedPondId].setStyle({ color: '#1565c0', fillColor: '#42a5f5' });
  }

  selectedPondId = pondId;
  const pond = pondData[pondId];
  if (!pond) return;

  // ハイライト
  if (pondLayers[pondId]) {
    pondLayers[pondId].setStyle({ color: '#e53935', fillColor: '#ef9a9a' });
  }

  // サイドバー情報更新
  const infoEl = document.getElementById('pond-info');
  const latest = pond.timeseries.length > 0
    ? pond.timeseries[pond.timeseries.length - 1]
    : null;

  infoEl.innerHTML = `
    <h2>${pond.name}</h2>
    <div class="meta">${pond.region} ／ ID: ${pond.id}</div>
    ${latest ? `<div class="latest-area">最新水面面積: <strong>${latest.water_area_m2.toLocaleString()} ㎡</strong>（${latest.date}）</div>` : ''}
  `;

  // グラフ描画
  document.getElementById('no-selection').style.display = 'none';
  document.getElementById('chart').style.display = 'block';
  renderChart(pond);
}

function renderChart(pond) {
  const dates = pond.timeseries.map(d => d.date);
  const areas = pond.timeseries.map(d => d.water_area_m2);

  const trace = {
    x: dates,
    y: areas,
    mode: 'lines+markers',
    type: 'scatter',
    name: '水面面積',
    line: { color: '#1565c0', width: 2 },
    marker: { size: 5, color: '#1565c0' },
    hovertemplate: '%{x}<br>%{y:,.0f} ㎡<extra></extra>',
  };

  const layout = {
    title: {
      text: `${pond.name} 水面面積時系列`,
      font: { size: 13 },
    },
    xaxis: {
      title: '撮影日',
      type: 'date',
      tickformat: '%Y-%m',
    },
    yaxis: {
      title: '水面面積 (㎡)',
      rangemode: 'tozero',
    },
    margin: { t: 40, r: 10, b: 50, l: 60 },
    plot_bgcolor: '#f8f9fa',
    paper_bgcolor: '#fff',
    font: { size: 11 },
  };

  const config = {
    responsive: true,
    displayModeBar: false,
  };

  Plotly.newPlot('chart', [trace], layout, config);
}

function showNoSelection() {
  document.getElementById('pond-info').innerHTML = '<span style="color:#999;font-size:13px;">地図上の池をクリックしてください</span>';
  document.getElementById('no-selection').style.display = 'flex';
  document.getElementById('chart').style.display = 'none';
}

// GeoJSON ポリゴンをGEEアセットとは別途提供された場合に描画する関数
// async function fetchGeoJsonAndRender(data) {
//   const geoResp = await fetch('ponds.geojson');
//   const geojson = await geoResp.json();
//   L.geoJSON(geojson, {
//     style: { color: '#1565c0', fillColor: '#42a5f5', fillOpacity: 0.5, weight: 1.5 },
//     onEachFeature: (feature, layer) => {
//       const id = String(feature.properties.id);
//       pondLayers[id] = layer;
//       layer.on('click', () => selectPond(id));
//       if (pondData[id]) layer.bindTooltip(pondData[id].name);
//     },
//   }).addTo(map);
// }

document.addEventListener('DOMContentLoaded', init);
