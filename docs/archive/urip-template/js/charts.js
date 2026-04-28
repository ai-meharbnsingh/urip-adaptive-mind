/**
 * URIP - Chart.js Configurations
 * Semantic Gravity - Unified Risk Intelligence Platform
 */

// Chart.js default configuration
Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
Chart.defaults.color = '#64748B';
Chart.defaults.scale.grid.color = '#E2E8F0';
Chart.defaults.plugins.tooltip.backgroundColor = '#0D1B2A';
Chart.defaults.plugins.tooltip.padding = 12;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: '600' };
Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };

// Brand colors
const colors = {
  teal: '#1ABC9C',
  tealLight: '#2ECC71',
  navy: '#0D1B2A',
  red: '#E74C3C',
  orange: '#E67E22',
  yellow: '#F1C40F',
  green: '#27AE60',
  gray: '#94A3B8',
  purple: '#9B59B6',
  blue: '#3498DB',
  pink: '#E91E63'
};

// Domain colors for doughnut chart
const domainColors = [
  colors.teal,      // Endpoint
  colors.blue,      // Cloud
  colors.purple,    // Network
  colors.orange,    // Application
  colors.pink,      // Identity
  colors.yellow     // OT
];

// Source colors for bar chart
const sourceColors = [
  colors.teal,      // Spotlight
  colors.blue,      // EASM
  colors.purple,    // CNAPP
  colors.orange,    // OT
  colors.red,       // VAPT
  colors.green,     // Threat Intel
  colors.yellow,    // CERT-In
  colors.pink,      // Bug Bounty
  colors.gray       // SoC
];

/**
 * Initialize all charts on the dashboard
 */
function initializeDashboardCharts() {
  initRiskByDomainChart();
  initRiskTrendChart();
  initRiskBySourceChart();
}

/**
 * Risk by Domain Doughnut Chart
 */
function initRiskByDomainChart() {
  const ctx = document.getElementById('riskByDomainChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Endpoint', 'Cloud', 'Network', 'Application', 'Identity', 'OT'],
      datasets: [{
        data: [45, 32, 28, 38, 22, 15],
        backgroundColor: domainColors,
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((context.raw / total) * 100).toFixed(1);
              return `${context.label}: ${context.raw} risks (${percentage}%)`;
            }
          }
        }
      }
    }
  });
}

/**
 * Risk Trend Line Chart
 */
function initRiskTrendChart() {
  const ctx = document.getElementById('riskTrendChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      datasets: [
        {
          label: 'Critical',
          data: [28, 26, 24, 22, 20, 18],
          borderColor: colors.red,
          backgroundColor: colors.red,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: 'High',
          data: [52, 50, 48, 45, 42, 40],
          borderColor: colors.orange,
          backgroundColor: colors.orange,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: 'Medium',
          data: [85, 82, 80, 78, 75, 72],
          borderColor: colors.yellow,
          backgroundColor: colors.yellow,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: 'Total',
          data: [195, 188, 182, 175, 168, 162],
          borderColor: colors.teal,
          backgroundColor: colors.teal,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 20,
            font: { size: 12 }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: false,
          grid: {
            borderDash: [4, 4]
          },
          ticks: {
            font: { size: 11 }
          }
        },
        x: {
          grid: {
            display: false
          },
          ticks: {
            font: { size: 11 }
          }
        }
      }
    }
  });
}

/**
 * Risk by Source Bar Chart
 */
function initRiskBySourceChart() {
  const ctx = document.getElementById('riskBySourceChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Spotlight', 'EASM', 'CNAPP', 'OT', 'VAPT', 'Threat Intel', 'CERT-In', 'Bug Bounty', 'SoC'],
      datasets: [{
        label: 'Risks Detected',
        data: [32, 28, 25, 22, 20, 18, 15, 12, 10],
        backgroundColor: sourceColors,
        borderRadius: 6,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.raw} risks detected`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            borderDash: [4, 4]
          },
          ticks: {
            font: { size: 11 }
          }
        },
        x: {
          grid: {
            display: false
          },
          ticks: {
            font: { size: 10 },
            maxRotation: 45,
            minRotation: 45
          }
        }
      }
    }
  });
}

/**
 * Executive Summary Chart (for Reports page)
 */
function initExecutiveChart() {
  const ctx = document.getElementById('executiveChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Critical', 'High', 'Medium', 'Low'],
      datasets: [{
        label: 'Open Risks',
        data: [18, 40, 72, 32],
        backgroundColor: [colors.red, colors.orange, colors.yellow, colors.green],
        borderRadius: 8,
        borderSkipped: false
      },
      {
        label: 'Resolved (MTD)',
        data: [12, 28, 45, 38],
        backgroundColor: [colors.red + '80', colors.orange + '80', colors.yellow + '80', colors.green + '80'],
        borderRadius: 8,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          align: 'end'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            borderDash: [4, 4]
          }
        },
        x: {
          grid: {
            display: false
          }
        }
      }
    }
  });
}

/**
 * Initialize charts when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
  initializeDashboardCharts();
  initExecutiveChart();
});

// Export functions for use in other scripts
window.URIPCharts = {
  initializeDashboardCharts,
  initRiskByDomainChart,
  initRiskTrendChart,
  initRiskBySourceChart,
  initExecutiveChart,
  colors
};
