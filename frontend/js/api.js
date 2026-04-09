/**
 * URIP - Central API Client
 * JWT handling, fetch wrapper, and shared notification utility.
 */
(function () {
  'use strict';

  var URIP = window.URIP || {};

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
    var headers = options.headers || {};

    var token = localStorage.getItem('urip_token');
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    options.headers = headers;

    var url = '/api' + path;
    var response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      showNotification('Network Error', 'Unable to reach the server. Please check your connection.', 'error');
      throw err;
    }

    if (response.status === 401) {
      localStorage.removeItem('urip_token');
      localStorage.removeItem('urip_user');
      window.location.href = 'index.html';
      return;
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
      'position:fixed;top:20px;right:20px;background:#fff;border-radius:8px;' +
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
  window.URIP = URIP;
})();
