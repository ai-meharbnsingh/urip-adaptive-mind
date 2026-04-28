/**
 * URIP — Tenant Onboarding Admin UI (P1.2)
 *
 * Super-admin only.
 * - Lists all tenants via GET /api/admin/tenants
 * - "New tenant" modal -> POST /api/admin/tenants
 * - Click row -> admin-tenant-detail.html?slug=...
 *
 * Depends on: api.js, theming.js
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  function showError(msg) {
    $('tenantsLoading').style.display = 'none';
    $('tenantsContent').style.display = 'none';
    $('tenantsError').style.display = 'flex';
    $('tenantsErrorMsg').textContent = msg;
  }

  function showContent() {
    $('tenantsLoading').style.display = 'none';
    $('tenantsError').style.display = 'none';
    $('tenantsContent').style.display = 'block';
  }

  function fmtDate(iso) {
    if (!iso) return '–';
    try {
      var d = new Date(iso);
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (_e) {
      return iso;
    }
  }

  function renderTable(tenants) {
    var tbody = $('tenantsTableBody');
    tbody.textContent = '';

    if (!tenants || tenants.length === 0) {
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.setAttribute('colspan', '6');
      var es = document.createElement('div');
      es.className = 'empty-state';
      var icon = document.createElement('div');
      icon.className = 'empty-state-icon';
      var i = document.createElement('i');
      i.className = 'fas fa-building';
      icon.appendChild(i);
      es.appendChild(icon);
      var title = document.createElement('div');
      title.className = 'empty-state-title';
      title.textContent = 'No tenants yet';
      es.appendChild(title);
      var sub = document.createElement('div');
      sub.style.cssText = 'color:#64748B;font-size:0.875rem;margin-top:0.25rem';
      sub.textContent = 'Click "New tenant" to onboard your first tenant.';
      es.appendChild(sub);
      td.appendChild(es);
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    tenants.forEach(function (t) {
      var tr = document.createElement('tr');
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', function (e) {
        // Don't navigate if user clicked an action button
        if (e.target.closest('.action-btn')) return;
        window.location.href = 'admin-tenant-detail.html?slug=' + encodeURIComponent(t.slug);
      });

      // Name
      var tdName = document.createElement('td');
      var nameDiv = document.createElement('div');
      nameDiv.style.fontWeight = '500';
      nameDiv.textContent = t.name || '–';
      tdName.appendChild(nameDiv);
      tr.appendChild(tdName);

      // Slug
      var tdSlug = document.createElement('td');
      var slugCode = document.createElement('code');
      slugCode.style.cssText = 'font-family:"SF Mono",monospace;font-size:0.8125rem;color:#475569;background:#F0F4F8;padding:0.125rem 0.5rem;border-radius:4px';
      slugCode.textContent = t.slug || '–';
      tdSlug.appendChild(slugCode);
      tr.appendChild(tdSlug);

      // Domain
      var tdDomain = document.createElement('td');
      tdDomain.style.cssText = 'font-size:0.8125rem;color:#64748B';
      tdDomain.textContent = t.domain || '–';
      tr.appendChild(tdDomain);

      // Status
      var tdStatus = document.createElement('td');
      var statusBadge = document.createElement('span');
      statusBadge.className = 'badge ' + (t.is_active ? 'badge-low' : 'badge-default');
      statusBadge.textContent = t.is_active ? 'Active' : 'Inactive';
      tdStatus.appendChild(statusBadge);
      tr.appendChild(tdStatus);

      // Created
      var tdCreated = document.createElement('td');
      tdCreated.style.cssText = 'font-size:0.8125rem;color:#64748B';
      tdCreated.textContent = fmtDate(t.created_at);
      tr.appendChild(tdCreated);

      // Actions
      var tdActions = document.createElement('td');
      var actions = document.createElement('div');
      actions.className = 'action-btns';

      var viewBtn = document.createElement('button');
      viewBtn.className = 'action-btn view';
      viewBtn.title = 'Open tenant';
      var viewIcon = document.createElement('i');
      viewIcon.className = 'fas fa-arrow-right';
      viewBtn.appendChild(viewIcon);
      viewBtn.addEventListener('click', function () {
        window.location.href = 'admin-tenant-detail.html?slug=' + encodeURIComponent(t.slug);
      });
      actions.appendChild(viewBtn);

      tdActions.appendChild(actions);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  async function loadTenants() {
    $('tenantsLoading').style.display = 'flex';
    $('tenantsContent').style.display = 'none';
    $('tenantsError').style.display = 'none';

    try {
      var tenants = await window.URIP.apiFetch('/admin/tenants');
      renderTable(tenants || []);
      showContent();
    } catch (err) {
      var msg;
      if (err && err.status === 403) {
        msg = 'Super-admin access required to view tenants.';
      } else {
        msg = (err && err.body && err.body.detail) ||
              (err && err.message) ||
              'Failed to load tenants.';
      }
      showError(msg);
    }
  }

  // ---------------------------------------------------------------------------
  // New tenant modal
  // ---------------------------------------------------------------------------

  function openNewTenantModal() {
    $('newTenantModal').style.display = 'flex';
    $('tn_name').focus();
  }

  function closeNewTenantModal() {
    $('newTenantModal').style.display = 'none';
    $('newTenantForm').reset();
  }

  function deriveSlug(name) {
    return (name || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .substring(0, 100);
  }

  async function submitNewTenant(e) {
    e.preventDefault();

    var name = $('tn_name').value.trim();
    var slug = $('tn_slug').value.trim().toLowerCase();
    var domain = $('tn_domain').value.trim();
    var email = $('tn_email').value.trim();

    if (!name || !slug || !domain) {
      window.URIP.showNotification('Validation Error', 'Name, slug and domain are required.', 'error');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(slug)) {
      window.URIP.showNotification('Validation Error', 'Slug must contain only lowercase letters, digits, and hyphens.', 'error');
      return;
    }

    var payload = { name: name, slug: slug, domain: domain };
    if (email) payload.primary_contact_email = email;

    var btn = $('submitNewTenant');
    var originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = 'Creating...';

    try {
      await window.URIP.apiFetch('/admin/tenants', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      window.URIP.showNotification('Tenant Created', 'Tenant "' + name + '" created.', 'success');
      closeNewTenantModal();
      loadTenants();
    } catch (err) {
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) ||
                'Failed to create tenant.';
      if (err && err.status === 409) {
        msg = 'A tenant with slug "' + slug + '" already exists.';
      } else if (err && err.status === 403) {
        msg = 'Super-admin access required to create a tenant.';
      }
      window.URIP.showNotification('Create Failed', msg, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('tenantsContent')) return; // not on this page

    loadTenants();

    $('btnNewTenant').addEventListener('click', openNewTenantModal);
    $('closeNewTenant').addEventListener('click', closeNewTenantModal);
    $('cancelNewTenant').addEventListener('click', closeNewTenantModal);
    $('newTenantModal').addEventListener('click', function (e) {
      if (e.target === e.currentTarget) closeNewTenantModal();
    });
    $('newTenantForm').addEventListener('submit', submitNewTenant);

    // Auto-derive slug from name (until user manually edits the slug field)
    var slugTouched = false;
    $('tn_slug').addEventListener('input', function () { slugTouched = true; });
    $('tn_name').addEventListener('input', function () {
      if (!slugTouched) {
        $('tn_slug').value = deriveSlug($('tn_name').value);
      }
    });

    // Esc closes modal
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && $('newTenantModal').style.display !== 'none') {
        closeNewTenantModal();
      }
    });
  });
})();
