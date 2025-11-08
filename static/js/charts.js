// static/js/charts.js
// usage: include Chart.js CDN in template, then call initResultsChart(canvasId, labels, data)
function initResultsChart(canvasId, labels, data){
  const ctx = document.getElementById(canvasId);
  if(!ctx) return;
  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Votes',
        data: data,
        backgroundColor: labels.map((_,i)=>`rgba(11,94,215,${0.65 - i*0.05})`),
        borderColor: 'rgba(11,94,215,1)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      scales: {
        y:{ beginAtZero:true, ticks:{precision:0} }
      },
      plugins:{ legend:{ display:false } }
    }
  });
  return chart;
}
