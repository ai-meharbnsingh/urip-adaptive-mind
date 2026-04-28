(function () {
  'use strict';

  async function loadFindings() {
    var tbody = document.getElementById('findingsBody');
    var status = document.getElementById('filterStatus').value;
    var severity = document.getElementById('filterSeverity').value;
    var cloud = document.getElementById('filterCloud').value;
    var qs = '';
    if (status) qs += '&status=' + encodeURIComponent(status);
    if (severity) qs += '&severity=' + encodeURIComponent(severity);
    if (cloud) qs += '&cloud_provider=' + encodeURIComponent(cloud);
    try {
      var data = await URIP.apiFetch('/cspm/findings?limit=50' + qs, { silent: true });
      var items = data && data.items ? data.items : [];
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No findings match your filters.</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      items.forEach(function (item) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td>' + item.control_code + '</td>' +
          '<td>' + item.title + '</td>' +
          '<td><span class="badge badge-' + item.severity + '">' + item.severity + '</span></td>' +
          '<td><span class="badge badge-' + (item.status === 'pass' ? 'success' : item.status === 'fail' ? 'fail' : 'gray') + '">' + item.status + '</span></td>' +
          '<td>' + new Date(item.run_at).toLocaleString() + '</td>';
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center">Error loading findings.</td></tr>';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderSidebar('cspm-findings');
    loadFindings();
    document.getElementById('btnFilter').addEventListener('click', loadFindings);
  });
})();
