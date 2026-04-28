/**
 * URIP - Central API Client
 * JWT handling, fetch wrapper, and shared notification utility.
 */
(function () {
  'use strict';

  var URIP = window.URIP || {};

  // API base URL: use relative /api for all environments (handled by Vercel rewrites in prod)
  var API_BASE = '/api';

  /**
   * Wraps fetch with JWT auth and base-path prepending.
   * On 401, redirects to login page.
   *
   * @param {string} path  - API path (e.g. "/risks")
   * @param {object} [options] - Standard fetch options
   * @returns {Promise<any>} Parsed JSON response
   */
  async function apiFetch(path, options) {
    options = options || {};
    var silent = options.silent || false;
    delete options.silent;
    var retries = (typeof options.retries === 'number') ? options.retries : 2; // up to 3 attempts incl. first
    delete options.retries;
    var headers = options.headers || {};

    var token = localStorage.getItem('urip_token');
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    options.headers = headers;

    var url = API_BASE + path;
    var response;
    var attempt = 0;
    while (true) {
      try {
        response = await fetch(url, options);
        break;
      } catch (err) {
        attempt++;
        if (attempt > retries) {
          if (!silent) {
            showNotification('Network Error', 'Unable to reach the server. Please check your connection.', 'error');
          }
          throw err;
        }
        // Backoff: 250ms, 500ms, 1000ms
        await new Promise(function (r) { setTimeout(r, 250 * Math.pow(2, attempt - 1)); });
      }
    }

    if (response.status === 401) {
      localStorage.removeItem('urip_token');
      localStorage.removeItem('urip_user');
      // Avoid infinite loop on /auth/me at boot of login page
      if (window.location.pathname.indexOf('index.html') === -1 &&
          window.location.pathname !== '/' && !silent) {
        window.location.href = 'index.html';
      }
      var err401 = new Error('Unauthorized');
      err401.status = 401;
      throw err401;
    }

    if (response.status === 403) {
      var bodyTxt;
      try { bodyTxt = await response.json(); } catch (_e) { bodyTxt = { detail: 'Module not enabled' }; }
      if (!silent) {
        showNotification('Module not enabled', bodyTxt.detail || 'You don\'t have access to this module.', 'error');
      }
      var e403 = new Error(bodyTxt.detail || 'Forbidden');
      e403.status = 403;
      e403.body = bodyTxt;
      throw e403;
    }

    if (!response.ok) {
      var errorBody;
      try {
        errorBody = await response.json();
      } catch (_e) {
        errorBody = { detail: response.statusText };
      }
      var err = new Error(errorBody.detail || 'Request failed');
      err.status = response.status;
      err.body = errorBody;
      throw err;
    }

    // Some endpoints may return 204 No Content
    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Cached current user — populated by getCurrentUser(); refreshed on demand
  // ---------------------------------------------------------------------------
  var _userCache = null;

  async function getCurrentUser(opts) {
    opts = opts || {};
    if (_userCache && !opts.refresh) return _userCache;
    // Prefer fresh /auth/me when JWT is present
    var token = null;
    try { token = localStorage.getItem('urip_token'); } catch (_e) { /* ignore */ }
    if (!token) {
      // Fallback to whatever is in storage (legacy)
      try { _userCache = JSON.parse(localStorage.getItem('urip_user') || 'null'); }
      catch (_e) { _userCache = null; }
      return _userCache;
    }
    try {
      var me = await apiFetch('/auth/me', { silent: true });
      if (me && (me.email || me.full_name)) {
        _userCache = me;
        try { localStorage.setItem('urip_user', JSON.stringify(me)); } catch (_e) {}
      }
    } catch (_err) {
      // Fall back to cached storage value if /auth/me unavailable
      try { _userCache = JSON.parse(localStorage.getItem('urip_user') || 'null'); }
      catch (_e) { _userCache = null; }
    }
    return _userCache;
  }

  function getTenantBranding() {
    return (URIP.branding) || null;
  }

  /**
   * Show a toast notification (replaces all duplicated notification functions).
   *
   * @param {string} title
   * @param {string} message
   * @param {string} [type] - "success" | "error" | "info" (default "info")
   */
  function showNotification(title, message, type) {
    type = type || 'info';

    // Inject animation keyframes once
    if (!document.getElementById('urip-toast-styles')) {
      var style = document.createElement('style');
      style.id = 'urip-toast-styles';
      style.textContent =
        '@keyframes uripSlideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}' +
        '@keyframes uripSlideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}';
      document.head.appendChild(style);
    }

    var iconMap = {
      success: 'fa-check-circle',
      error: 'fa-times-circle',
      info: 'fa-info-circle'
    };
    var colorMap = {
      success: '#27AE60',
      error: '#E74C3C',
      info: '#1ABC9C'
    };

    var toast = document.createElement('div');
    toast.style.cssText =
      'position:fixed;top:20px;right:20px;background:var(--u-card,#fff);color:var(--u-fg,#1E293B);border-radius:8px;' +
      'padding:16px 20px;box-shadow:0 10px 40px rgba(0,0,0,0.2);z-index:10000;' +
      'min-width:300px;max-width:420px;animation:uripSlideIn 0.3s ease';

    var wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex;align-items:flex-start;gap:12px';

    var icon = document.createElement('i');
    icon.className = 'fas ' + (iconMap[type] || iconMap.info);
    icon.style.cssText = 'color:' + (colorMap[type] || colorMap.info) + ';font-size:20px;margin-top:2px';

    var textBlock = document.createElement('div');

    var titleEl = document.createElement('div');
    titleEl.style.cssText = 'font-weight:600;color:#1E293B;margin-bottom:4px';
    titleEl.textContent = title;

    var msgEl = document.createElement('div');
    msgEl.style.cssText = 'font-size:14px;color:#64748B';
    msgEl.textContent = message;

    textBlock.appendChild(titleEl);
    textBlock.appendChild(msgEl);
    wrapper.appendChild(icon);
    wrapper.appendChild(textBlock);
    toast.appendChild(wrapper);

    document.body.appendChild(toast);

    setTimeout(function () {
      toast.style.animation = 'uripSlideOut 0.3s ease';
      setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, 4000);
  }

  URIP.apiFetch = apiFetch;
  URIP.showNotification = showNotification;
  URIP.getCurrentUser = getCurrentUser;
  URIP.getTenantBranding = getTenantBranding;
  URIP.API_BASE = API_BASE;
  window.URIP = URIP;
})();
