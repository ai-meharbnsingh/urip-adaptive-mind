(function () {
  'use strict';

  async function loadControlDetail() {
    var params = new URLSearchParams(window.location.search);
    var id = params.get('id');
    var body = document.getElementById('controlDetailBody');
    if (!id) {
      body.innerHTML = '<p class="text-gray">No control selected. Go to <a href="cspm-findings.html">Findings</a> to select one.</p>';
      return;
    }
    try {
      var item = await URIP.apiFetch('/cspm/findings/' + encodeURIComponent(id), { silent: true });
      document.getElementById('controlTitle').textContent = item.control_code + ' — ' + item.title;
      document.getElementById('controlSubtitle').textContent = item.description || '';
      var html = '<div style="display:grid;gap:1rem">' +
        '<div><strong>Status:</strong> <span class="badge badge-' + (item.status === 'pass' ? 'success' : item.status === 'fail' ? 'fail' : 'gray') + '">' + item.status + '</span></div>' +
        '<div><strong>Severity:</strong> <span class="badge badge-' + item.severity + '">' + item.severity + '</span></div>' +
        '<div><strong>Cloud Account:</strong> ' + (item.cloud_account_id || '—') + '</div>' +
        '<div><strong>Run At:</strong> ' + new Date(item.run_at).toLocaleString() + '</div>' +
        '<div><strong>Failing Resources:</strong> ' + (item.failing_resource_ids && item.failing_resource_ids.length ? item.failing_resource_ids.join(', ') : 'None') + '</div>' +
        '<div><strong>Evidence:</strong><pre style="background:#f8fafc;padding:1rem;border-radius:8px;overflow:auto">' + JSON.stringify(item.evidence || {}, null, 2) + '</pre></div>' +
        '</div>';
      body.innerHTML = html;
    } catch (e) {
      body.innerHTML = '<p class="text-gray">Error loading control detail.</p>';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderSidebar('cspm-control-detail');
    loadControlDetail();
  });
})();
