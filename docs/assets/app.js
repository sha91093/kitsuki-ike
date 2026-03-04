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
  if (data.updated_at) {
    document.getElementById('updated-at').textContent =
      `最終更新: ${data.updated_at.replace('T', ' ')} UTC`;
  }

  data.ponds.forEach(pond => {
    pondData[pond.id] = pond;
  });

  data.ponds.forEach(pond => {
    // 座標がない池はスキップ
    if (pond.lat == null || pond.lng == null) return;

    const layer = L.circleMarker([pond.lat, pond.lng], {
      radius: 8,
      color: '#1565c0',
      fillColor: '#42a5f5',
      fillOpacity: 0.7,
      weight: 1.5,
    });

    const tooltipText = `${pond.name}（${pond.tiiki} ${pond.ooaza}）`;
    layer.bindTooltip(tooltipText, { permanent: false, direction: 'top' });
    layer.on('click', () => selectPond(pond.id));
    layer.addTo(map);

    pondLayers[pond.id] = layer;
  });

  showNoSelection();
}

function selectPond(pondId) {
  if (selectedPondId && pondLayers[selectedPondId]) {
    pondLayers[selectedPondId].setStyle({ color: '#1565c0', fillColor: '#42a5f5' });
  }

  selectedPondId = pondId;
  const pond = pondData[pondId];
  if (!pond) return;

  if (pondLayers[pondId]) {
    pondLayers[pondId].setStyle({ color: '#e53935', fillColor: '#ef9a9a' });
  }

  const latest = pond.timeseries && pond.timeseries.length > 0
    ? pond.timeseries[pond.timeseries.length - 1]
    : null;

  const areaHaStr = pond.area_ha != null ? `${pond.area_ha} ha` : '—';
  const waterAreaStr = latest
    ? `${latest.water_area_m2.toLocaleString()} ㎡（${latest.date}）`
    : 'データなし';

  document.getElementById('pond-info').innerHTML = `
    <h2>${pond.name}</h2>
    <table class="info-table">
      <tr><th>地域</th><td>${pond.tiiki || '—'}</td></tr>
      <tr><th>大字</th><td>${pond.ooaza || '—'}</td></tr>
      <tr><th>池面積</th><td>${areaHaStr}</td></tr>
      <tr><th>最新水面</th><td><strong>${waterAreaStr}</strong></td></tr>
    </table>
  `;

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

  Plotly.newPlot('chart', [trace], layout, { responsive: true, displayModeBar: false });
}

function showNoSelection() {
  document.getElementById('pond-info').innerHTML =
    '<span style="color:#999;font-size:13px;">地図上の池をクリックしてください</span>';
  document.getElementById('no-selection').style.display = 'flex';
  document.getElementById('chart').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', init);
