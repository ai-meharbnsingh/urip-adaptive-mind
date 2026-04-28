/**
 * URIP - Filter and Table Functionality
 * Semantic Gravity - Unified Risk Intelligence Platform
 */

// Risk data for the register
const riskData = [
  { id: 'RISK-2024-001', finding: 'Log4j RCE Vulnerability', source: 'VAPT', domain: 'Application', cvss: 10.0, severity: 'Critical', asset: 'Payment Gateway API', owner: 'App Team', status: 'Open', sla: '2024-01-15', slaHours: 12 },
  { id: 'RISK-2024-002', finding: 'Open S3 Bucket Exposure', source: 'CNAPP', domain: 'Cloud', cvss: 7.5, severity: 'High', asset: 's3://customer-data-prod', owner: 'Cloud Team', status: 'In Progress', sla: '2024-01-18', slaHours: 72 },
  { id: 'RISK-2024-003', finding: 'IDOR in User Profile API', source: 'Bug Bounty', domain: 'Application', cvss: 6.5, severity: 'Medium', asset: 'User Service API', owner: 'App Team', status: 'Open', sla: '2024-01-25', slaHours: 168 },
  { id: 'RISK-2024-004', finding: 'Shared Admin Password Detected', source: 'CyberArk', domain: 'Identity', cvss: 9.8, severity: 'Critical', asset: 'Domain Admin Accounts', owner: 'IAM Team', status: 'Open', sla: '2024-01-14', slaHours: 6 },
  { id: 'RISK-2024-005', finding: 'OT Protocol Vulnerability', source: 'Armis', domain: 'OT', cvss: 8.2, severity: 'High', asset: 'HMI Controller #3', owner: 'OT Team', status: 'In Progress', sla: '2024-01-20', slaHours: 96 },
  { id: 'RISK-2024-006', finding: 'Shadow IT Application', source: 'Zscaler CASB', domain: 'Cloud', cvss: 5.3, severity: 'Medium', asset: 'unsanctioned-app.com', owner: 'Cloud Team', status: 'Accepted', sla: '2024-01-30', slaHours: 240 },
  { id: 'RISK-2024-007', finding: 'CVE-2024-1234 - Apache Struts', source: 'CERT-In', domain: 'Application', cvss: 9.8, severity: 'Critical', asset: 'Internal Portal', owner: 'App Team', status: 'Open', sla: '2024-01-14', slaHours: 8 },
  { id: 'RISK-2024-008', finding: 'Phishing Campaign Detected', source: 'CrowdStrike Falcon', domain: 'Endpoint', cvss: 7.8, severity: 'High', asset: 'Executive Laptops', owner: 'Infra Team', status: 'In Progress', sla: '2024-01-16', slaHours: 48 },
  { id: 'RISK-2024-009', finding: 'Unpatched Windows Server', source: 'Spotlight', domain: 'Endpoint', cvss: 8.8, severity: 'High', asset: 'WS-2019-PROD-01', owner: 'Infra Team', status: 'Open', sla: '2024-01-17', slaHours: 60 },
  { id: 'RISK-2024-010', finding: 'Exposed Database Port', source: 'EASM', domain: 'Network', cvss: 7.4, severity: 'High', asset: 'PostgreSQL Prod', owner: 'Network Team', status: 'Open', sla: '2024-01-19', slaHours: 84 },
  { id: 'RISK-2024-011', finding: 'Weak SSL Configuration', source: 'VAPT', domain: 'Network', cvss: 5.8, severity: 'Medium', asset: 'Load Balancer', owner: 'Network Team', status: 'Accepted', sla: '2024-01-28', slaHours: 216 },
  { id: 'RISK-2024-012', finding: 'Suspicious Lateral Movement', source: 'SoC', domain: 'Network', cvss: 8.5, severity: 'High', asset: 'VLAN-Prod-Servers', owner: 'Network Team', status: 'In Progress', sla: '2024-01-16', slaHours: 36 },
  { id: 'RISK-2024-013', finding: 'Missing MFA on Admin Console', source: 'Forescout', domain: 'Identity', cvss: 7.2, severity: 'High', asset: 'Admin Portal', owner: 'IAM Team', status: 'Open', sla: '2024-01-18', slaHours: 72 },
  { id: 'RISK-2024-014', finding: 'Outdated Firmware on Switch', source: 'Threat Intel', domain: 'Network', cvss: 6.8, severity: 'Medium', asset: 'Core Switch-01', owner: 'Network Team', status: 'Open', sla: '2024-01-22', slaHours: 120 },
  { id: 'RISK-2024-015', finding: 'Malware Signature Detected', source: 'CrowdStrike Falcon', domain: 'Endpoint', cvss: 9.2, severity: 'Critical', asset: 'Finance Workstation', owner: 'Infra Team', status: 'Open', sla: '2024-01-14', slaHours: 4 }
];

// Acceptance workflow data
const acceptanceData = [
  { 
    id: 'RISK-2024-006', 
    title: 'Shadow IT Application', 
    cvss: 5.3, 
    severity: 'Medium',
    requestedBy: 'Cloud Team', 
    requesterRole: 'Cloud Security Lead',
    date: '2024-01-10',
    recommendation: 'Compensating Control suggested. Implement CASB monitoring and DLP policies. Re-review in 90 days.',
    justification: 'Application is used by marketing team for campaign analytics. Business critical with no immediate alternative. Risk mitigated through data loss prevention controls.',
    compensatingControls: ['DLP policies active', 'CASB monitoring enabled', 'Quarterly access review'],
    risk: 'Data exfiltration through unsanctioned cloud app'
  },
  { 
    id: 'RISK-2024-011', 
    title: 'Weak SSL Configuration', 
    cvss: 5.8, 
    severity: 'Medium',
    requestedBy: 'Network Team', 
    requesterRole: 'Network Security Engineer',
    date: '2024-01-09',
    recommendation: 'Accept with exception. Schedule maintenance window for TLS 1.3 upgrade. Re-review in 60 days.',
    justification: 'Legacy application compatibility requires TLS 1.2. Upgrade scheduled for next maintenance window. No known active exploits for current configuration.',
    compensatingControls: ['WAF rules in place', 'Traffic monitoring active', 'Maintenance scheduled'],
    risk: 'Man-in-the-middle attack on legacy protocol'
  },
  { 
    id: 'RISK-2024-018', 
    title: 'Unpatched Development Server', 
    cvss: 4.2, 
    severity: 'Low',
    requestedBy: 'DevOps Team', 
    requesterRole: 'DevOps Lead',
    date: '2024-01-11',
    recommendation: 'Accept with monitoring. Isolated network segment. Re-review in 30 days.',
    justification: 'Development environment isolated from production. No sensitive data present. Patch scheduled with next sprint deployment.',
    compensatingControls: ['Network isolation', 'No production data', 'Scheduled patching'],
    risk: 'Lateral movement from dev to prod'
  }
];

// Current page and filters
let currentPage = 1;
const itemsPerPage = 10;
let filteredData = [...riskData];

/**
 * Initialize filters and event listeners
 */
document.addEventListener('DOMContentLoaded', function() {
  initializeFilters();
  initializeSearch();
  initializePagination();
  renderRiskTable();
  initializeAcceptanceWorkflow();
});

/**
 * Initialize filter dropdowns
 */
function initializeFilters() {
  const severityFilter = document.getElementById('severityFilter');
  const sourceFilter = document.getElementById('sourceFilter');
  const domainFilter = document.getElementById('domainFilter');
  const statusFilter = document.getElementById('statusFilter');
  const ownerFilter = document.getElementById('ownerFilter');

  const filters = [severityFilter, sourceFilter, domainFilter, statusFilter, ownerFilter];
  
  filters.forEach(filter => {
    if (filter) {
      filter.addEventListener('change', applyFilters);
    }
  });
}

/**
 * Initialize search functionality
 */
function initializeSearch() {
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', debounce(applyFilters, 300));
  }
}

/**
 * Apply all filters to the data
 */
function applyFilters() {
  const severity = document.getElementById('severityFilter')?.value || 'all';
  const source = document.getElementById('sourceFilter')?.value || 'all';
  const domain = document.getElementById('domainFilter')?.value || 'all';
  const status = document.getElementById('statusFilter')?.value || 'all';
  const owner = document.getElementById('ownerFilter')?.value || 'all';
  const search = document.getElementById('searchInput')?.value.toLowerCase() || '';

  filteredData = riskData.filter(risk => {
    const matchesSeverity = severity === 'all' || risk.severity.toLowerCase() === severity;
    const matchesSource = source === 'all' || risk.source.toLowerCase().includes(source);
    const matchesDomain = domain === 'all' || risk.domain.toLowerCase() === domain;
    const matchesStatus = status === 'all' || risk.status.toLowerCase().replace(' ', '-') === status;
    const matchesOwner = owner === 'all' || risk.owner.toLowerCase().replace(' ', '-') === owner;
    const matchesSearch = search === '' || 
      risk.finding.toLowerCase().includes(search) ||
      risk.id.toLowerCase().includes(search) ||
      risk.asset.toLowerCase().includes(search);

    return matchesSeverity && matchesSource && matchesDomain && matchesStatus && matchesOwner && matchesSearch;
  });

  currentPage = 1;
  renderRiskTable();
  updatePagination();
}

/**
 * Render the risk register table
 */
function renderRiskTable() {
  const tbody = document.getElementById('riskTableBody');
  if (!tbody) return;

  const start = (currentPage - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  const pageData = filteredData.slice(start, end);

  if (pageData.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="12" class="empty-state">
          <div class="empty-state-icon">
            <i class="fas fa-search"></i>
          </div>
          <div class="empty-state-title">No risks found</div>
          <div class="empty-state-text">Try adjusting your filters or search criteria</div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = pageData.map(risk => {
    const severityClass = risk.severity.toLowerCase();
    const cvssClass = risk.cvss >= 9 ? 'critical' : risk.cvss >= 7 ? 'high' : risk.cvss >= 4 ? 'medium' : 'low';
    const statusClass = risk.status.toLowerCase().replace(' ', '-');
    const isAccepted = risk.status === 'Accepted';
    const slaClass = risk.slaHours <= 24 ? 'danger' : risk.slaHours <= 72 ? 'warning' : 'safe';
    
    return `
      <tr class="${isAccepted ? 'accepted' : ''}">
        <td><span class="risk-id">${risk.id}</span></td>
        <td>
          <div class="risk-finding">
            <div class="risk-finding-name">${risk.finding}</div>
            <div class="risk-finding-domain">${risk.domain}</div>
          </div>
        </td>
        <td>
          <div class="risk-source">
            <span class="source-icon"><i class="fas fa-shield-alt"></i></span>
            ${risk.source}
          </div>
        </td>
        <td>${risk.domain}</td>
        <td><span class="cvss-score cvss-${cvssClass}">${risk.cvss}</span></td>
        <td><span class="badge badge-${severityClass}">${risk.severity}</span></td>
        <td><span class="risk-asset" title="${risk.asset}">${risk.asset}</span></td>
        <td>
          <div class="risk-owner">
            <span class="owner-avatar">${risk.owner.split(' ').map(w => w[0]).join('')}</span>
            ${risk.owner}
          </div>
        </td>
        <td><span class="status-tag status-${statusClass}">${risk.status}</span></td>
        <td>
          <div class="risk-sla">
            <span class="sla-date">${risk.sla}</span>
            <span class="sla-remaining ${slaClass}">${risk.slaHours}h remaining</span>
          </div>
        </td>
        <td>
          ${isAccepted ? '<span class="excluded-tag"><i class="fas fa-ban"></i> Excluded from Reports</span>' : ''}
        </td>
        <td>
          <div class="action-btns">
            <button class="action-btn view" title="View Details"><i class="fas fa-eye"></i></button>
            <button class="action-btn assign" title="Assign"><i class="fas fa-user-plus"></i></button>
            ${!isAccepted ? `<button class="action-btn accept" title="Accept Risk"><i class="fas fa-check-circle"></i></button>` : ''}
            <button class="action-btn close" title="Close"><i class="fas fa-times-circle"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Initialize pagination
 */
function initializePagination() {
  const prevBtn = document.getElementById('prevPage');
  const nextBtn = document.getElementById('nextPage');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        renderRiskTable();
        updatePagination();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const totalPages = Math.ceil(filteredData.length / itemsPerPage);
      if (currentPage < totalPages) {
        currentPage++;
        renderRiskTable();
        updatePagination();
      }
    });
  }
}

/**
 * Update pagination controls
 */
function updatePagination() {
  const pageInfo = document.getElementById('pageInfo');
  const prevBtn = document.getElementById('prevPage');
  const nextBtn = document.getElementById('nextPage');
  const totalPages = Math.ceil(filteredData.length / itemsPerPage);

  if (pageInfo) {
    pageInfo.textContent = `Page ${currentPage} of ${totalPages || 1}`;
  }

  if (prevBtn) {
    prevBtn.disabled = currentPage === 1;
  }

  if (nextBtn) {
    nextBtn.disabled = currentPage === totalPages || totalPages === 0;
  }
}

/**
 * Initialize acceptance workflow
 */
function initializeAcceptanceWorkflow() {
  const requestList = document.getElementById('requestList');
  const detailPanel = document.getElementById('detailPanel');

  if (!requestList) return;

  // Render request list
  renderRequestList();

  // Select first request by default
  if (acceptanceData.length > 0) {
    selectRequest(0);
  }
}

/**
 * Render acceptance request list
 */
function renderRequestList() {
  const requestList = document.getElementById('requestList');
  if (!requestList) return;

  requestList.innerHTML = acceptanceData.map((request, index) => {
    const severityClass = request.severity.toLowerCase();
    return `
      <div class="request-item" data-index="${index}" onclick="selectRequest(${index})">
        <div class="request-header">
          <span class="risk-id">${request.id}</span>
          <span class="badge badge-${severityClass}">${request.severity}</span>
        </div>
        <div class="request-title">${request.title}</div>
        <div class="request-meta">
          <span><i class="fas fa-user"></i> ${request.requestedBy}</span>
          <span><i class="fas fa-calendar"></i> ${request.date}</span>
          <span><i class="fas fa-chart-line"></i> CVSS: ${request.cvss}</span>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Select a request and show details
 */
function selectRequest(index) {
  const request = acceptanceData[index];
  if (!request) return;

  // Update active state in list
  document.querySelectorAll('.request-item').forEach((item, i) => {
    item.classList.toggle('active', i === index);
  });

  // Update detail panel
  const detailPanel = document.getElementById('detailPanel');
  if (!detailPanel) return;

  const severityClass = request.severity.toLowerCase();
  
  detailPanel.innerHTML = `
    <div class="detail-panel-header">
      <div class="flex items-center justify-between mb-2">
        <span class="risk-id">${request.id}</span>
        <span class="badge badge-${severityClass}">${request.severity}</span>
      </div>
      <h3 class="text-lg font-semibold">${request.title}</h3>
    </div>
    <div class="detail-panel-body">
      <div class="detail-section">
        <div class="detail-section-title">Risk Details</div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <div class="text-sm text-gray-500">CVSS Score</div>
            <div class="text-lg font-semibold">${request.cvss}</div>
          </div>
          <div>
            <div class="text-sm text-gray-500">Requested By</div>
            <div class="font-medium">${request.requestedBy}</div>
            <div class="text-xs text-gray-500">${request.requesterRole}</div>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">AI Recommendation</div>
        <div class="recommendation-box">
          <p><i class="fas fa-robot text-teal mr-2"></i>${request.recommendation}</p>
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Business Justification</div>
        <p class="text-sm text-gray-600">${request.justification}</p>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Compensating Controls</div>
        <ul class="list-disc list-inside text-sm text-gray-600">
          ${request.compensatingControls.map(control => `<li>${control}</li>`).join('')}
        </ul>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Residual Risk</div>
        <p class="text-sm text-gray-600">${request.risk}</p>
      </div>

      <div class="acceptance-actions">
        <button class="btn btn-primary" onclick="approveRequest('${request.id}')">
          <i class="fas fa-check"></i> Approve
        </button>
        <button class="btn btn-danger" onclick="rejectRequest('${request.id}')">
          <i class="fas fa-times"></i> Reject
        </button>
      </div>

      <div class="audit-trail">
        <div class="detail-section-title">Audit Trail</div>
        <div class="audit-item">
          <div class="audit-icon"><i class="fas fa-user"></i></div>
          <div class="audit-content">
            <div class="audit-text">Risk acceptance requested by ${request.requestedBy}</div>
            <div class="audit-time">${request.date} 09:30 AM</div>
          </div>
        </div>
        <div class="audit-item">
          <div class="audit-icon"><i class="fas fa-robot"></i></div>
          <div class="audit-content">
            <div class="audit-text">AI recommendation generated</div>
            <div class="audit-time">${request.date} 09:31 AM</div>
          </div>
        </div>
        <div class="audit-item">
          <div class="audit-icon"><i class="fas fa-clock"></i></div>
          <div class="audit-content">
            <div class="audit-text">Assigned to HoD for review</div>
            <div class="audit-time">${request.date} 09:35 AM</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Approve a risk acceptance request
 */
function approveRequest(id) {
  showNotification('Success', `Risk ${id} has been approved and will be excluded from reports.`, 'success');
}

/**
 * Reject a risk acceptance request
 */
function rejectRequest(id) {
  showNotification('Rejected', `Risk ${id} acceptance has been rejected.`, 'error');
}

/**
 * Show notification toast
 */
function showNotification(title, message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `notification-toast notification-${type}`;
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    border-radius: 8px;
    padding: 16px 20px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    z-index: 1000;
    min-width: 300px;
    animation: slideIn 0.3s ease;
  `;
  
  const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'times-circle' : 'info-circle';
  const color = type === 'success' ? '#27AE60' : type === 'error' ? '#E74C3C' : '#1ABC9C';
  
  toast.innerHTML = `
    <div style="display: flex; align-items: flex-start; gap: 12px;">
      <i class="fas fa-${icon}" style="color: ${color}; font-size: 20px; margin-top: 2px;"></i>
      <div>
        <div style="font-weight: 600; color: #1E293B; margin-bottom: 4px;">${title}</div>
        <div style="font-size: 14px; color: #64748B;">${message}</div>
      </div>
    </div>
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/**
 * Debounce utility function
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);

// Export functions
window.URIPFilters = {
  applyFilters,
  renderRiskTable,
  selectRequest,
  approveRequest,
  rejectRequest,
  showNotification
};
