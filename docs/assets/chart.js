'use strict';

const YEAR_COLORS = [
  '#3b82f6', // blue
  '#f97316', // orange
  '#10b981', // emerald
  '#a855f7', // purple
  '#ef4444', // red
  '#eab308', // yellow
  '#06b6d4', // cyan
  '#ec4899', // pink
];

async function init() {
  const params = new URLSearchParams(location.search);
  const pondId = params.get('id');
  if (!pondId) {
    document.getElementById('pond-name').textContent = 'IDが指定されていません';
    return;
  }

  let data;
  try {
    const resp = await fetch('data.json');
    if (!resp.ok) throw new Error('data.json 読み込み失敗');
    data = await resp.json();
  } catch (e) {
    document.getElementById('pond-name').textContent = 'データ読み込みエラー';
    console.error(e);
    return;
  }

  const pond = data.ponds.find(p => String(p.id) === String(pondId));
  if (!pond) {
    document.getElementById('pond-name').textContent = `ID ${pondId} の池が見つかりません`;
    return;
  }

  renderMeta(pond);
  if (!pond.timeseries || pond.timeseries.length === 0) {
    document.getElementById('chart').style.display = 'none';
    document.getElementById('no-data').style.display = 'flex';
    return;
  }
  renderChart(pond);
}

function renderMeta(pond) {
  document.title = `${pond.name} — 杵築市 水面面積モニタリング`;
  document.getElementById('pond-name').textContent = pond.name;

  // 直近の非ゼロデータを最新値として使用
  const latest = pond.timeseries.slice().reverse().find(d => d.water_area_m2 > 0)
    ?? pond.timeseries[pond.timeseries.length - 1]
    ?? null;
  const latestHa = latest ? (latest.water_area_m2 / 10000).toFixed(4) : null;

  const chips = [
    { label: '地域',         value: pond.tiiki   || '—' },
    { label: '大字',         value: pond.ooaza   || '—' },
    { label: '登録面積',     value: pond.area_ha != null ? `${pond.area_ha} ha` : '—' },
    { label: '最新水面面積', value: latestHa ? `${latestHa} ha（${latest.date}）` : 'データなし' },
  ];

  document.getElementById('meta-bar').innerHTML = chips.map(c => `
    <div class="meta-chip">
      <span class="label">${c.label}</span>
      <span class="value">${c.value}</span>
    </div>
  `).join('');
}

function renderChart(pond) {
  // 年ごとに撮影日の実測値をそのまま整理（平均なし）
  const byYear = {};
  pond.timeseries.forEach(d => {
    const [y, m, day] = d.date.split('-');
    const year = parseInt(y, 10);
    if (!byYear[year]) byYear[year] = [];
    byYear[year].push({
      origDate: d.date,
      // 年比較のため月日を基準年2000へ正規化（2000年は閏年なので2/29も安全）
      xDate: `2000-${m}-${day}`,
      ha: d.water_area_m2 / 10000,
    });
  });

  const years = Object.keys(byYear).map(Number).sort();

  // 年ごとのトレース（撮影日ごとの実測値）
  const traces = years.map((year, i) => {
    const color = YEAR_COLORS[i % YEAR_COLORS.length];
    const pts = byYear[year].sort((a, b) => a.xDate.localeCompare(b.xDate));
    return {
      x: pts.map(p => p.xDate),
      y: pts.map(p => p.ha),
      customdata: pts.map(p => p.origDate),
      mode: 'lines+markers',
      name: `${year}年`,
      line:   { color, width: 2 },
      marker: { color, size: 6, symbol: 'circle',
                line: { color: '#fff', width: 1.5 } },
      hovertemplate:
        `<b>${year}年</b> %{customdata}<br>水面面積: <b>%{y:.4f} ha</b><extra></extra>`,
    };
  });

  // 登録面積を参照線として追加（y軸レンジ計算には含めない）
  if (pond.area_ha != null) {
    traces.push({
      x: ['2000-01-01', '2000-12-31'],
      y: [pond.area_ha, pond.area_ha],
      mode: 'lines',
      name: `登録面積 (${pond.area_ha} ha)`,
      line: { color: '#cbd5e1', width: 1.5, dash: 'dot' },
      hoverinfo: 'skip',
    });
  }

  // 実データの最大値からy軸レンジを決定（参照線は除外）
  const dataMaxHa = Math.max(
    0,
    ...traces
      .filter(t => !t.name.startsWith('登録面積'))
      .flatMap(t => t.y.filter(v => v != null))
  );
  const yMax = dataMaxHa > 0 ? dataMaxHa * 1.25 : 1;

  const layout = {
    font: { family: '"Noto Sans JP", sans-serif', size: 12, color: '#4a5568' },
    paper_bgcolor: '#fff',
    plot_bgcolor:  '#fafbfc',
    margin: { t: 30, r: 20, b: 70, l: 70 },
    legend: {
      orientation: 'h',
      x: 0, y: -0.2,
      font: { size: 12 },
    },
    xaxis: {
      title: { text: '月', standoff: 14 },
      type: 'date',
      tickformat: '%-m月',
      dtick: 'M1',
      gridcolor: '#edf2f7',
      linecolor: '#e2e8f0',
      tickfont: { size: 12 },
    },
    yaxis: {
      title: { text: '水面面積 (ha)', standoff: 12 },
      gridcolor: '#edf2f7',
      linecolor: '#e2e8f0',
      range: [0, yMax],
      tickfont: { size: 12 },
      tickformat: '.3f',
    },
    hovermode: 'closest',
    hoverlabel: {
      bgcolor: '#1a202c',
      bordercolor: '#1a202c',
      font: { color: '#fff', size: 12, family: '"Noto Sans JP", sans-serif' },
    },
  };

  const config = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
    displaylogo: false,
    locale: 'ja',
  };

  Plotly.newPlot('chart', traces, layout, config);
}

document.addEventListener('DOMContentLoaded', init);
