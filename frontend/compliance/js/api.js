/**
 * URIP COMPLIANCE — API Client
 *
 * Wraps fetch() against the Compliance backend (default port 8001 standalone,
 * or proxied behind URIP shell when integrated).
 *
 * Token policy:
 *   - INTEGRATED mode: JWT supplied by URIP, stored as `urip_token` in localStorage.
 *   - STANDALONE mode: Compliance issues its own JWT, stored as `compliance_token`.
 *   - Auditor portal: JWT stored as `auditor_jwt` in sessionStorage.
 * The wrapper checks all three in priority order so the same code paths work
 * across deployment modes.
 *
 * Notification: showNotification(title, message, type) — toast in top-right.
 */
(function () {
  'use strict';

  var COMPLIANCE = window.COMPLIANCE || {};

  // API base — pluggable per environment.
  // Local dev: standalone backend on :8001. Production: served via reverse proxy.
  function detectApiBase() {
    if (window.COMPLIANCE_API_BASE) return window.COMPLIANCE_API_BASE;
    var override = localStorage.getItem('compliance_api_base');
    if (override) return override.replace(/\/$/, '');
    var host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '') {
      return 'http://localhost:8001';
    }
    // Production: same origin, proxy strips /compliance-api prefix
    return window.location.origin + '/compliance-api';
  }

  var API_BASE = detectApiBase();

  function getToken() {
    // Try in priority order — auditor session first (most restrictive),
    // then compliance standalone, then URIP integrated.
    return sessionStorage.getItem('auditor_jwt') ||
           localStorage.getItem('compliance_token') ||
           localStorage.getItem('urip_token') ||
           null;
  }

  /**
   * Wrapped fetch with JWT, JSON handling, and error normalisation.
   *
   * @param {string} path     - API path (e.g. "/frameworks")
   * @param {object} [options] - { method, body, headers, silent, raw, query }
   * @returns {Promise<any>} Parsed JSON, or raw Response if `raw: true`
   */
  async function apiFetch(path, options) {
    options = options || {};
    var silent = options.silent === true;
    var raw = options.raw === true;
    delete options.silent;
    delete options.raw;

    var headers = options.headers || {};
    var token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (!(options.body instanceof FormData) && options.body && typeof options.body !== 'string') {
      options.body = JSON.stringify(options.body);
    }
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    options.headers = headers;

    // Append query params if provided
    var url = API_BASE + path;
    if (options.query && typeof options.query === 'object') {
      var qs = Object.keys(options.query)
        .filter(function (k) { return options.query[k] !== undefined && options.query[k] !== null && options.query[k] !== ''; })
        .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(options.query[k]); })
        .join('&');
      if (qs) url += (url.indexOf('?') > -1 ? '&' : '?') + qs;
      delete options.query;
    }

    var response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      if (!silent) {
        showNotification('Network Error', 'Unable to reach the compliance backend at ' + API_BASE, 'error');
      }
      throw err;
    }

    if (response.status === 401) {
      // Don't blow away auditor session on 401 of a non-auditor endpoint
      if (sessionStorage.getItem('auditor_jwt') && path.indexOf('/auditor') === 0) {
        sessionStorage.removeItem('auditor_jwt');
        if (!silent) showNotification('Session expired', 'Your auditor session has ended.', 'error');
        return Promise.reject(new Error('Unauthorized'));
      }
      // Otherwise normal logout flow
      if (!silent) showNotification('Authentication required', 'Please sign in again.', 'error');
      // Don't auto-redirect — caller decides (auditor vs admin).
      var err401 = new Error('Unauthorized'); err401.status = 401; throw err401;
    }

    if (raw) return response;

    if (!response.ok) {
      var body;
      try { body = await response.json(); } catch (_) { body = { detail: response.statusText }; }
      var err = new Error(body.detail || ('Request failed: ' + response.status));
      err.status = response.status;
      err.body = body;
      if (!silent) showNotification('Error', err.message, 'error');
      throw err;
    }

    if (response.status === 204) return null;
    var ct = response.headers.get('content-type') || '';
    if (ct.indexOf('application/json') > -1) return response.json();
    return response;
  }

  // ---------------------------------------------------------------------------
  // Toast notifications
  // ---------------------------------------------------------------------------

  function showNotification(title, message, type) {
    type = type || 'info';
    if (!document.getElementById('compliance-toast-styles')) {
      var style = document.createElement('style');
      style.id = 'compliance-toast-styles';
      style.textContent =
        '@keyframes complianceSlideIn{from{transform:translateX(110%);opacity:0}to{transform:translateX(0);opacity:1}}' +
        '@keyframes complianceSlideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(110%);opacity:0}}';
      document.head.appendChild(style);
    }

    var iconMap = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle' };
    var colorMap = { success: '#16A34A', error: '#DC2626', info: '#1ABC9C', warning: '#D97706' };

    var toast = document.createElement('div');
    toast.style.cssText =
      'position:fixed;top:20px;right:20px;background:#fff;border-radius:10px;' +
      'padding:14px 18px;box-shadow:0 10px 40px rgba(0,0,0,0.18);z-index:10000;' +
      'min-width:320px;max-width:440px;animation:complianceSlideIn 0.3s ease;' +
      'border-left:4px solid ' + (colorMap[type] || colorMap.info);

    var wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex;align-items:flex-start;gap:12px';

    var icon = document.createElement('i');
    icon.className = 'fas ' + (iconMap[type] || iconMap.info);
    icon.style.cssText = 'color:' + (colorMap[type] || colorMap.info) + ';font-size:18px;margin-top:2px';

    var textBlock = document.createElement('div');
    textBlock.style.cssText = 'flex:1;min-width:0';

    var titleEl = document.createElement('div');
    titleEl.style.cssText = 'font-weight:600;color:#1E293B;margin-bottom:2px;font-size:14px';
    titleEl.textContent = title;

    var msgEl = document.createElement('div');
    msgEl.style.cssText = 'font-size:13px;color:#64748B;line-height:1.4';
    msgEl.textContent = message;

    textBlock.appendChild(titleEl);
    textBlock.appendChild(msgEl);
    wrapper.appendChild(icon);
    wrapper.appendChild(textBlock);
    toast.appendChild(wrapper);

    document.body.appendChild(toast);

    setTimeout(function () {
      toast.style.animation = 'complianceSlideOut 0.3s ease';
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    }, 4000);
  }

  // ---------------------------------------------------------------------------
  // Small DOM helpers shared across pages
  // ---------------------------------------------------------------------------

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function faIcon(cls) {
    var i = document.createElement('i');
    i.className = 'fas ' + cls;
    return i;
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (_) { return iso; }
  }

  function formatDateOnly(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (_) { return iso; }
  }

  function relativeTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    var diffMs = Date.now() - d.getTime();
    var sec = Math.round(diffMs / 1000);
    if (sec < 60) return sec + 's ago';
    var min = Math.round(sec / 60);
    if (min < 60) return min + 'm ago';
    var hr = Math.round(min / 60);
    if (hr < 24) return hr + 'h ago';
    var day = Math.round(hr / 24);
    if (day < 7) return day + 'd ago';
    return formatDateOnly(iso);
  }

  /**
   * Render skeleton placeholders inside an element.
   */
  function renderSkeleton(el, kind, count) {
    el.innerHTML = '';
    count = count || 3;
    for (var i = 0; i < count; i++) {
      var s = document.createElement('div');
      s.className = 'skeleton skeleton-' + (kind || 'row');
      el.appendChild(s);
    }
  }

  function renderEmptyState(el, icon, title, body) {
    el.innerHTML = '';
    var wrap = document.createElement('div');
    wrap.className = 'empty-state';
    var i = document.createElement('div'); i.className = 'empty-state-icon';
    var fa = document.createElement('i'); fa.className = 'fas ' + (icon || 'fa-inbox'); i.appendChild(fa);
    var h = document.createElement('h3'); h.textContent = title || 'Nothing to show';
    var p = document.createElement('p'); p.textContent = body || '';
    wrap.appendChild(i); wrap.appendChild(h); wrap.appendChild(p);
    el.appendChild(wrap);
  }

  // ---------------------------------------------------------------------------
  // Modal helper
  // ---------------------------------------------------------------------------

  function openModal(opts) {
    // opts: { title, body (HTMLElement|string), footer (HTMLElement[]|null), onClose }
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    var modal = document.createElement('div');
    modal.className = 'modal';

    var header = document.createElement('div');
    header.className = 'modal-header';
    var title = document.createElement('div');
    title.className = 'modal-title';
    title.textContent = opts.title || '';
    var close = document.createElement('button');
    close.className = 'modal-close';
    close.appendChild(faIcon('fa-times'));
    header.appendChild(title);
    header.appendChild(close);

    var body = document.createElement('div');
    body.className = 'modal-body';
    if (typeof opts.body === 'string') body.innerHTML = opts.body;
    else if (opts.body instanceof HTMLElement) body.appendChild(opts.body);

    modal.appendChild(header);
    modal.appendChild(body);

    if (opts.footer && opts.footer.length) {
      var footer = document.createElement('div');
      footer.className = 'modal-footer';
      opts.footer.forEach(function (f) { footer.appendChild(f); });
      modal.appendChild(footer);
    }

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    function doClose() {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      if (typeof opts.onClose === 'function') opts.onClose();
    }
    close.addEventListener('click', doClose);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) doClose();
    });
    return { close: doClose, overlay: overlay, modal: modal };
  }

  // Expose
  COMPLIANCE.apiFetch = apiFetch;
  COMPLIANCE.showNotification = showNotification;
  COMPLIANCE.el = el;
  COMPLIANCE.faIcon = faIcon;
  COMPLIANCE.escapeHtml = escapeHtml;
  COMPLIANCE.formatDate = formatDate;
  COMPLIANCE.formatDateOnly = formatDateOnly;
  COMPLIANCE.relativeTime = relativeTime;
  COMPLIANCE.renderSkeleton = renderSkeleton;
  COMPLIANCE.renderEmptyState = renderEmptyState;
  COMPLIANCE.openModal = openModal;
  COMPLIANCE.API_BASE = API_BASE;
  COMPLIANCE.getToken = getToken;
  window.COMPLIANCE = COMPLIANCE;
})();
