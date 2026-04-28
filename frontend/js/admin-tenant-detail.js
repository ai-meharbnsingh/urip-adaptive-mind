/**
 * URIP — Tenant Detail Admin UI (P1.2 cont'd)
 *
 * Super-admin only. Slug comes from ?slug=... query string.
 *
 * Features:
 *  - Show tenant info  (GET /api/admin/tenants/{slug})
 *  - Edit white-label branding (PATCH /api/admin/tenants/{slug})
 *      logo_url, primary_color, secondary_color, app_name, is_active
 *  - Provision tenant admin user (POST /api/admin/tenants/{slug}/users)
 *  - Live preview of branding before save
 *  - "Preview branding" button — applies to current page locally (no save)
 *
 * Depends on: api.js, theming.js
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  var slug = null;
  var tenant = null;

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function getSlugFromQuery() {
    try {
      var p = new URLSearchParams(window.location.search);
      var s = p.get('slug');
      return s ? s.toLowerCase() : null;
    } catch (_e) {
      return null;
    }
  }

  function fmtDate(iso) {
    if (!iso) return '–';
    try {
      var d = new Date(iso);
      return d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (_e) {
      return iso;
    }
  }

  function isHexColor(s) {
    return typeof s === 'string' && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(s);
  }

  function showError(msg) {
    $('detailLoading').style.display = 'none';
    $('detailContent').style.display = 'none';
    $('detailError').style.display = 'flex';
    $('detailErrorMsg').textContent = msg;
  }

  function showContent() {
    $('detailLoading').style.display = 'none';
    $('detailError').style.display = 'none';
    $('detailContent').style.display = 'block';
  }

  // ---------------------------------------------------------------------------
  // Render tenant info + branding form
  // ---------------------------------------------------------------------------

  function renderTenant(t) {
    tenant = t;
    var s = t.settings || {};

    $('pageTitle').textContent = t.name || t.slug;
    $('pageSubtitle').textContent = t.domain + '  ·  slug: ' + t.slug;

    var statusBadge = $('statusBadge');
    statusBadge.textContent = t.is_active ? 'Active' : 'Inactive';
    statusBadge.className = 'badge ' + (t.is_active ? 'badge-low' : 'badge-default');

    $('info_id').textContent = t.id || '–';
    $('info_name').textContent = t.name || '–';
    $('info_slug').textContent = t.slug || '–';
    $('info_domain').textContent = t.domain || '–';
    $('info_created').textContent = fmtDate(t.created_at);
    $('info_contact').textContent = s.primary_contact_email || '–';

    // Populate branding form
    $('b_app_name').value = s.app_name || '';
    $('b_logo_url').value = s.logo_url || '';
    $('b_primary').value = s.primary_color || '';
    $('b_secondary').value = s.secondary_color || '';
    if (isHexColor(s.primary_color)) $('b_primary_picker').value = s.primary_color;
    if (isHexColor(s.secondary_color)) $('b_secondary_picker').value = s.secondary_color;
    $('b_is_active').checked = !!t.is_active;

    renderBrandingPreview();
  }

  function renderBrandingPreview() {
    var name = $('b_app_name').value.trim() || 'URIP';
    var logoUrl = $('b_logo_url').value.trim();
    var primary = $('b_primary').value.trim();
    var secondary = $('b_secondary').value.trim();

    if (!isHexColor(primary)) primary = '#1ABC9C';
    if (!isHexColor(secondary)) secondary = '#0D1B2A';

    $('brandingPreviewBar').style.background = primary;
    $('brandingPreview').style.borderColor = secondary;
    $('brandingPreviewTitle').textContent = name;

    var logoEl = $('brandingPreviewLogo');
    logoEl.style.background = secondary;
    logoEl.style.color = primary;
    logoEl.textContent = '';
    if (logoUrl && /^https?:\/\//.test(logoUrl)) {
      var img = document.createElement('img');
      img.src = logoUrl;
      img.alt = name + ' logo';
      img.style.cssText = 'max-width:100%;max-height:32px';
      img.addEventListener('error', function () {
        logoEl.textContent = '';
        var i = document.createElement('i');
        i.className = 'fas fa-shield-alt';
        logoEl.appendChild(i);
      });
      logoEl.appendChild(img);
    } else {
      var i = document.createElement('i');
      i.className = 'fas fa-shield-alt';
      logoEl.appendChild(i);
    }
  }

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  async function loadTenant() {
    $('detailLoading').style.display = 'flex';
    $('detailContent').style.display = 'none';
    $('detailError').style.display = 'none';

    try {
      var t = await window.URIP.apiFetch('/admin/tenants/' + encodeURIComponent(slug));
      renderTenant(t);
      showContent();
    } catch (err) {
      var msg;
      if (err && err.status === 404) {
        msg = 'Tenant "' + slug + '" not found.';
      } else if (err && err.status === 403) {
        msg = 'Super-admin access required to view this tenant.';
      } else {
        msg = (err && err.body && err.body.detail) ||
              (err && err.message) ||
              'Failed to load tenant.';
      }
      showError(msg);
    }
  }

  // ---------------------------------------------------------------------------
  // Save branding (PATCH /admin/tenants/{slug})
  // ---------------------------------------------------------------------------

  async function saveBranding(e) {
    e.preventDefault();

    var payload = {};
    var appName = $('b_app_name').value.trim();
    var logoUrl = $('b_logo_url').value.trim();
    var primary = $('b_primary').value.trim();
    var secondary = $('b_secondary').value.trim();
    var isActive = $('b_is_active').checked;

    // Validation
    var errs = [];
    if (logoUrl && !/^https?:\/\//.test(logoUrl)) {
      errs.push('Logo URL must start with http:// or https://');
    }
    if (primary && !isHexColor(primary)) {
      errs.push('Primary color must be a hex value like #1ABC9C.');
    }
    if (secondary && !isHexColor(secondary)) {
      errs.push('Secondary color must be a hex value like #0D1B2A.');
    }
    if (errs.length) {
      window.URIP.showNotification('Validation Error', errs.join(' '), 'error');
      return;
    }

    // Send only fields that have a value (omit empties so we don't clobber to "")
    if (appName) payload.app_name = appName;
    if (logoUrl) payload.logo_url = logoUrl;
    if (primary) payload.primary_color = primary;
    if (secondary) payload.secondary_color = secondary;
    payload.is_active = isActive;

    var btn = $('btnSaveBranding');
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      // NOTE: backend TenantUpdate only accepts logo_url, primary_color, app_name, is_active.
      // secondary_color is NOT in the schema. We still send it so when backend adds the
      // field it just works; for now Pydantic will reject unknown fields with 422 — handle that.
      var updated = await window.URIP.apiFetch('/admin/tenants/' + encodeURIComponent(slug), {
        method: 'PATCH',
        body: JSON.stringify(payload)
      });
      if (updated) {
        renderTenant(updated);
      }
      window.URIP.showNotification('Saved', 'Branding updated.', 'success');

      // Invalidate branding cache so next page load re-fetches
      if (window.URIP.theming && window.URIP.theming.clearCache) {
        window.URIP.theming.clearCache();
      }
    } catch (err) {
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) || 'Failed to save branding.';
      if (err && err.status === 422 && payload.secondary_color) {
        // Retry without secondary_color (backend doesn't know about it yet)
        delete payload.secondary_color;
        try {
          var updated2 = await window.URIP.apiFetch('/admin/tenants/' + encodeURIComponent(slug), {
            method: 'PATCH',
            body: JSON.stringify(payload)
          });
          if (updated2) renderTenant(updated2);
          window.URIP.showNotification(
            'Partially Saved',
            'Branding saved. NOTE: secondary_color was rejected by backend — schema needs to add the field.',
            'info'
          );
          return;
        } catch (_retryErr) {
          msg = 'Branding save failed even after retry.';
        }
      }
      window.URIP.showNotification('Save Failed', msg, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
    }
  }

  // ---------------------------------------------------------------------------
  // Provision admin user (POST /admin/tenants/{slug}/users)
  // ---------------------------------------------------------------------------

  async function provisionUser(e) {
    e.preventDefault();

    var payload = {
      email: $('u_email').value.trim(),
      full_name: $('u_full_name').value.trim(),
      password: $('u_password').value,
      role: $('u_role').value
    };

    if (!payload.email || !payload.full_name || !payload.password) {
      window.URIP.showNotification('Validation Error', 'All fields are required.', 'error');
      return;
    }
    if (payload.password.length < 8) {
      window.URIP.showNotification('Validation Error', 'Password must be at least 8 characters.', 'error');
      return;
    }

    var btn = $('btnProvision');
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = 'Provisioning...';

    try {
      var resp = await window.URIP.apiFetch('/admin/tenants/' + encodeURIComponent(slug) + '/users', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      window.URIP.showNotification(
        'User Created',
        'Admin user ' + (resp.email || payload.email) + ' provisioned for tenant.',
        'success'
      );
      $('provisionForm').reset();
      $('u_role').value = 'ciso';
    } catch (err) {
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) || 'Failed to provision user.';
      if (err && err.status === 409) {
        msg = 'A user with that email already exists.';
      } else if (err && err.status === 403) {
        msg = 'Super-admin access required.';
      }
      window.URIP.showNotification('Provision Failed', msg, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
    }
  }

  // ---------------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('detailContent')) return;

    slug = getSlugFromQuery();
    if (!slug || !/^[a-z0-9-]+$/.test(slug)) {
      showError('No tenant slug provided. Pass ?slug=... in the URL.');
      return;
    }

    loadTenant();

    // Live preview wiring
    ['b_app_name', 'b_logo_url', 'b_primary', 'b_secondary'].forEach(function (id) {
      $(id).addEventListener('input', renderBrandingPreview);
    });

    // Color picker syncs text input
    $('b_primary_picker').addEventListener('input', function () {
      $('b_primary').value = $('b_primary_picker').value;
      renderBrandingPreview();
    });
    $('b_secondary_picker').addEventListener('input', function () {
      $('b_secondary').value = $('b_secondary_picker').value;
      renderBrandingPreview();
    });
    $('b_primary').addEventListener('input', function () {
      if (isHexColor($('b_primary').value)) $('b_primary_picker').value = $('b_primary').value;
    });
    $('b_secondary').addEventListener('input', function () {
      if (isHexColor($('b_secondary').value)) $('b_secondary_picker').value = $('b_secondary').value;
    });

    $('btnResetBranding').addEventListener('click', function () {
      if (tenant) renderTenant(tenant);
    });

    $('brandingForm').addEventListener('submit', saveBranding);
    $('provisionForm').addEventListener('submit', provisionUser);

    $('btnViewModules').addEventListener('click', function () {
      window.location.href = 'admin-modules.html?tenant=' + encodeURIComponent(slug);
    });

    $('btnImpersonate').addEventListener('click', function () {
      // Apply current form's branding to the current page locally + persist tenant slug
      if (window.URIP.theming) {
        window.URIP.theming.setTenantSlug(slug);
        window.URIP.theming.apply({
          app_name: $('b_app_name').value.trim() || tenant.name || 'URIP',
          logo_url: $('b_logo_url').value.trim() || null,
          primary_color: $('b_primary').value.trim() || '#1ABC9C',
          secondary_color: $('b_secondary').value.trim() || '#0D1B2A'
        });
        window.URIP.showNotification('Preview applied', 'Branding applied to this page only (not saved).', 'info');
      }
    });
  });
})();
