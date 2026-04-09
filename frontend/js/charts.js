/**
 * URIP - Dashboard Charts (API-driven)
 * Fetches chart data from backend and renders via Chart.js.
 * Depends on: api.js (window.URIP.apiFetch), Chart.js global
 */
(function () {
  'use strict';

  // Domain color palette
  var DOMAIN_COLORS = [
    '#1ABC9C', // teal
    '#3498DB', // blue
    '#9B59B6', // purple
    '#E67E22', // orange
    '#E91E63', // pink
    '#F1C40F'  // yellow
  ];

  // Trend line colors
  var TREND_COLORS = {
    Critical: { border: '#E74C3C', bg: 'rgba(231,76,60,0.08)' },
    High:     { border: '#E67E22', bg: 'rgba(230,126,34,0.08)' },
    Medium:   { border: '#F1C40F', bg: 'rgba(241,196,15,0.08)' },
    Total:    { border: '#1ABC9C', bg: 'rgba(26,188,156,0.08)' }
  };

  // Chart.js defaults
  if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#64748B';
    Chart.defaults.plugins.tooltip.backgroundColor = '#0D1B2A';
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.titleFont = { weight: '600', size: 13 };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
  }

  /**
   * Risk by Domain - Doughnut chart
   */
  async function initRiskByDomainChart() {
    var canvas = document.getElementById('riskByDomainChart');
    if (!canvas) return;

    try {
      var data = await window.URIP.apiFetch('/dashboard/charts/by-domain');

      var chart = new Chart(canvas.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: data.labels,
          datasets: [{
            data: data.data,
            backgroundColor: DOMAIN_COLORS.slice(0, data.labels.length),
            borderWidth: 0,
            hoverOffset: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          plugins: {
            legend: { display: false }
          }
        }
      });

      // Update the legend below the chart
      var legendContainer = canvas.closest('.dashboard-card-body');
      if (legendContainer) {
        var existingLegend = legendContainer.querySelector('.chart-legend');
        if (existingLegend) {
          existingLegend.textContent = '';
          data.labels.forEach(function (label, idx) {
            var item = document.createElement('div');
            item.className = 'legend-item';

            var colorDot = document.createElement('span');
            colorDot.className = 'legend-color';
            colorDot.style.backgroundColor = DOMAIN_COLORS[idx] || '#94A3B8';
            item.appendChild(colorDot);

            var text = document.createElement('span');
            text.textContent = label + ' (' + data.data[idx] + ')';
            item.appendChild(text);

            existingLegend.appendChild(item);
          });
        }
      }

      return chart;
    } catch (err) {
      // Silently fail - dashboard can still work without charts
    }
  }

  /**
   * Risk Trend - Line chart (6 months default)
   */
  async function initRiskTrendChart() {
    var canvas = document.getElementById('riskTrendChart');
    if (!canvas) return;

    try {
      var data = await window.URIP.apiFetch('/dashboard/charts/trend?months=6');

      var datasets = data.datasets.map(function (ds) {
        var colors = TREND_COLORS[ds.label] || TREND_COLORS.Total;
        return {
          label: ds.label,
          data: ds.data,
          borderColor: colors.border,
          backgroundColor: colors.bg,
          borderWidth: 2,
          tension: 0.4,
          fill: ds.label === 'Total',
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: colors.border
        };
      });

      return new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            intersect: false,
            mode: 'index'
          },
          scales: {
            x: {
              grid: { display: false },
              border: { display: false }
            },
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(0,0,0,0.05)' },
              border: { display: false }
            }
          },
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: {
                boxWidth: 8,
                boxHeight: 8,
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 16,
                font: { size: 11 }
              }
            }
          }
        }
      });
    } catch (err) {
      // Silently fail
    }
  }

  /**
   * Risk by Source - Bar chart
   */
  async function initRiskBySourceChart() {
    var canvas = document.getElementById('riskBySourceChart');
    if (!canvas) return;

    try {
      var data = await window.URIP.apiFetch('/dashboard/charts/by-source');

      return new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: data.labels,
          datasets: [{
            data: data.data,
            backgroundColor: DOMAIN_COLORS.concat(DOMAIN_COLORS).slice(0, data.labels.length),
            borderRadius: 6,
            borderSkipped: false,
            barPercentage: 0.7
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              grid: { display: false },
              border: { display: false }
            },
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(0,0,0,0.05)' },
              border: { display: false }
            }
          },
          plugins: {
            legend: { display: false }
          }
        }
      });
    } catch (err) {
      // Silently fail
    }
  }

  // Expose
  window.initRiskByDomainChart = initRiskByDomainChart;
  window.initRiskTrendChart = initRiskTrendChart;
  window.initRiskBySourceChart = initRiskBySourceChart;
})();
