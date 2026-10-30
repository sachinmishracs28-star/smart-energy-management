const $ = id => document.getElementById(id);
const api = async (u, o) => (await fetch(u, o)).json();
const room = $('room');
const SUN = '#e8a317', LEAF = '#2f7d5b', PINE = '#12372a';

function lineChart(id, series) {
  return new Chart($(id), {
    type: 'line',
    data: { labels: [], datasets: series.map(([label, color]) => ({
      label, borderColor: color, backgroundColor: color + '22', fill: true,
      tension: .35, pointRadius: 0, data: [] })) },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      scales: { y: { beginAtZero: true }, x: { ticks: { maxTicksLimit: 8 } } } }
  });
}
function setChart(ch, labels, ...arrays) {
  ch.data.labels = labels;
  arrays.forEach((a, i) => ch.data.datasets[i].data = a);
  ch.update('none');
}

const live = lineChart('live', [['Power use', LEAF], ['Solar generation', SUN]]);
const fc = lineChart('fc', [['Predicted demand', PINE], ['Expected solar', SUN]]);
const mix = new Chart($('mix'), {
  type: 'doughnut',
  data: { labels: ['Solar', 'Grid'], datasets: [{ data: [0, 1], backgroundColor: [SUN, PINE] }] },
  options: { responsive: true, maintainAspectRatio: false, cutout: '62%' }
});

function drawFloors(rows) {
  $('floors').innerHTML = rows.map(r => {
    const max = Math.max(r.predicted, r.energy) * 1.4 || 1;
    const label = { normal: 'Normal', high: 'Above forecast', waste: 'Wasting energy' }[r.status];
    return `<div class="floor ${r.status}">
      <strong>${r.room}</strong>
      <div class="bar" title="Marker shows AI forecast">
        <i style="width:${r.energy / max * 100}%"></i><em style="left:${r.predicted / max * 100}%"></em></div>
      <div class="meta"><b>${r.energy} kW</b> (forecast ${r.predicted}) · ${r.temperature} °C · ${r.occupancy} people · ${r.lux} lux
        <span class="tag">${label}</span></div></div>`;
  }).join('');
}

async function refresh() {
  const sel = encodeURIComponent(room.value);
  const [s, l, h, f] = await Promise.all([api('/api/summary'), api('/api/latest'),
    api('/api/history?room=' + sel), api('/api/forecast?room=' + sel)]);
  $('k-total').textContent = s.total_kwh;
  $('k-solar').textContent = s.solar_kwh;
  $('k-cost').textContent = '₹' + s.cost;
  $('k-co2').textContent = s.co2_saved;
  $('k-score').textContent = s.score;
  $('k-predicted').textContent = f.demand[0].toFixed(2) + ' kW';
  $('k-hourly-co2').textContent = f.hourly_co2[0].toFixed(2) + ' kg';
  $('k-hourly-cost').textContent = '₹' + f.hourly_cost[0].toFixed(2);
  drawFloors(l);
  setChart(live, h.map(x => x.t), h.map(x => x.energy), h.map(x => x.solar));
  setChart(fc, f.labels, f.demand, f.solar);
  mix.data.datasets[0].data = [s.solar_kwh, s.grid_kwh]; mix.update('none');
  $('alerts').innerHTML = s.alerts.map(([lvl, msg]) => `<li class="${lvl}">${msg}</li>`).join('');
  $('model-info').textContent =
    `Random Forest trained on ${s.model.samples} readings. Average error ${s.model.mae} kW, R² ${s.model.r2}.`;
}

room.addEventListener('change', refresh);
$('retrain').addEventListener('click', async () => {
  $('model-info').textContent = 'Retraining…';
  await api('/api/retrain', { method: 'POST' });
  refresh();
});
refresh();
setInterval(refresh, 5000);
