(function () {
  'use strict';

  function scoreClass(score) {
    if (score >= 80) return 'high';
    if (score >= 50) return 'medium';
    return 'low';
  }

  async function loadScores() {
    try {
      var data = await URIP.apiFetch('/cspm/score', { silent: true });
      var items = data && data.items ? data.items : [];
      items.forEach(function (item) {
        var el = document.getElementById(item.cloud_provider + 'Score');
        if (el) {
          el.textContent = item.score + '%';
          var tile = document.getElementById(item.cloud_provider + 'ScoreTile');
          if (tile) {
            var icon = tile.querySelector('.action-tile-icon');
            icon.className = 'action-tile-icon icon-' + scoreClass(item.score);
          }
        }
      });
    } catch (e) {
      console.warn('Failed to load CSPM scores', e);
    }
  }

  async function loadFailingControls() {
    var tbody = document.getElementById('failingBody');
    try {
      var data = await URIP.apiFetch('/cspm/findings?status=fail&limit=10', { silent: true });
      var items = data && data.items ? data.items : [];
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No failing controls</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      items.forEach(function (item) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td>' + item.control_code + '</td>' +
          '<td><span class="badge badge-' + item.severity + '">' + item.severity + '</span></td>' +
          '<td>' + (item.cloud_account_id || '—') + '</td>' +
          '<td><span class="badge badge-fail">' + item.status + '</span></td>';
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center">Error loading</td></tr>';
    }
  }

  async function loadCloudAccounts() {
    var body = document.getElementById('cloudAccountsBody');
    try {
      var data = await URIP.apiFetch('/cspm/clouds', { silent: true });
      var items = data && data.items ? data.items : [];
      if (!items.length) {
        body.innerHTML = '<p class="text-gray">No clouds connected.</p>' +
          '<a href="#" class="btn btn-primary" onclick="showConnectModal();return false;">Connect a Cloud</a>';
        return;
      }
      body.innerHTML = '';
      items.forEach(function (item) {
        var div = document.createElement('div');
        div.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid var(--gray-200)';
        var status = item.configured ? '<span class="badge badge-success">Connected</span>' : '<span class="badge badge-gray">Not connected</span>';
        div.innerHTML = '<span><i class="fas fa-cloud"></i> ' + item.connector.toUpperCase() + '</span> ' + status;
        body.appendChild(div);
      });
    } catch (e) {
      body.innerHTML = '<p class="text-gray">Error loading accounts.</p>';
    }
  }

  async function scanNow() {
    try {
      var btn = document.getElementById('btnScanNow');
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning...';
      var data = await URIP.apiFetch('/cspm/scan-now', { method: 'POST' });
      URIP.showNotification('Scan Complete', 'Scanned: ' + (data.scanned || []).join(', '), 'success');
      loadScores();
      loadFailingControls();
    } catch (e) {
      URIP.showNotification('Scan Failed', e.message || 'Error', 'error');
    } finally {
      var btn2 = document.getElementById('btnScanNow');
      if (btn2) { btn2.disabled = false; btn2.innerHTML = '<i class="fas fa-play"></i> Scan Now'; }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderSidebar('cspm-dashboard');
    loadScores();
    loadFailingControls();
    loadCloudAccounts();
    document.getElementById('btnRefresh').addEventListener('click', function () {
      loadScores(); loadFailingControls(); loadCloudAccounts();
    });
    document.getElementById('btnScanNow').addEventListener('click', scanNow);
  });
})();
