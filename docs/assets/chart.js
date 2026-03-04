'use strict';

// 年ごとのカラーパレット（最大8年分）
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

const MONTH_LABELS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

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

  const latest = pond.timeseries.length > 0
    ? pond.timeseries[pond.timeseries.length - 1]
    : null;
  const latestHa = latest ? (latest.water_area_m2 / 10000).toFixed(4) : null;

  const chips = [
    { label: '地域',     value: pond.tiiki  || '—' },
    { label: '大字',     value: pond.ooaza  || '—' },
    { label: '登録面積', value: pond.area_ha != null ? `${pond.area_ha} ha` : '—' },
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
  // 時系列データを 年 → 月 → [値(ha)] に集計
  const byYear = {};
  pond.timeseries.forEach(d => {
    const [y, m] = d.date.split('-');
    const year  = parseInt(y, 10);
    const month = parseInt(m, 10);
    if (!byYear[year]) byYear[year] = {};
    if (!byYear[year][month]) byYear[year][month] = [];
    byYear[year][month].push(d.water_area_m2 / 10000);
  });

  const years = Object.keys(byYear).map(Number).sort();

  // 年ごとのトレース
  const traces = years.map((year, i) => {
    const color = YEAR_COLORS[i % YEAR_COLORS.length];
    const y = Array.from({ length: 12 }, (_, mi) => {
      const vals = byYear[year][mi + 1];
      if (!vals || vals.length === 0) return null;
      return vals.reduce((a, b) => a + b, 0) / vals.length;
    });
    return {
      x: MONTH_LABELS,
      y,
      mode: 'lines+markers',
      name: `${year}年`,
      connectgaps: true,
      line:   { color, width: 2.5, shape: 'spline' },
      marker: { color, size: 7, symbol: 'circle',
                line: { color: '#fff', width: 1.5 } },
      hovertemplate: `<b>${year}年 %{x}</b><br>水面面積: %{y:.4f} ha<extra></extra>`,
    };
  });

  // 登録面積を参照線として追加
  if (pond.area_ha != null) {
    traces.push({
      x: MONTH_LABELS,
      y: Array(12).fill(pond.area_ha),
      mode: 'lines',
      name: `登録面積 (${pond.area_ha} ha)`,
      line: { color: '#cbd5e1', width: 1.5, dash: 'dot' },
      hovertemplate: `登録面積: ${pond.area_ha} ha<extra></extra>`,
    });
  }

  const layout = {
    font: { family: '"Noto Sans JP", sans-serif', size: 12, color: '#4a5568' },
    paper_bgcolor: '#fff',
    plot_bgcolor:  '#fafbfc',
    margin: { t: 30, r: 20, b: 60, l: 70 },
    legend: {
      orientation: 'h',
      x: 0, y: -0.18,
      font: { size: 12 },
    },
    xaxis: {
      title: { text: '月', standoff: 12 },
      gridcolor: '#edf2f7',
      linecolor: '#e2e8f0',
      tickfont: { size: 12 },
      fixedrange: false,
    },
    yaxis: {
      title: { text: '水面面積 (ha)', standoff: 12 },
      gridcolor: '#edf2f7',
      linecolor: '#e2e8f0',
      rangemode: 'tozero',
      tickfont: { size: 12 },
      tickformat: '.3f',
    },
    hovermode: 'x unified',
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
