/**
 * VAPT Vendor Portal — API client.
 *
 * Wraps fetch() and handles:
 *  - VAPT vendor JWT in Authorization header (read from localStorage)
 *  - JSON request/response for ordinary endpoints
 *  - multipart/form-data for submission + retest endpoints
 *  - error normalization (turns 4xx/5xx into Error with .message)
 *
 * Public surface:
 *   VaptPortalApi.acceptInvitation(token)
 *   VaptPortalApi.getProfile()
 *   VaptPortalApi.listSubmissions(statusFilter)
 *   VaptPortalApi.getSubmission(id)
 *   VaptPortalApi.submitFinding(formData)
 *   VaptPortalApi.submitRetestResponse(submissionId, formData)
 *   VaptPortalApi.listNotifications()
 */
(function () {
  'use strict';

  var SESSION_KEY = 'urip_vapt_vendor_session';
  var API_PREFIX = '/api';

  function getJwt() {
    try {
      var raw = localStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      var p = JSON.parse(raw);
      return p && p.jwt ? p.jwt : null;
    } catch (_e) {
      return null;
    }
  }

  function buildUrl(path) {
    return API_PREFIX + path;
  }

  function parseError(resp) {
    return resp.text().then(function (txt) {
      var msg = 'Request failed (' + resp.status + ')';
      try {
        var body = JSON.parse(txt);
        if (body && body.detail) {
          msg = typeof body.detail === 'string'
                ? body.detail
                : JSON.stringify(body.detail);
        }
      } catch (_e) { /* not JSON */ }
      var err = new Error(msg);
      err.status = resp.status;
      throw err;
    });
  }

  function jsonFetch(method, path, body) {
    var headers = { 'Accept': 'application/json' };
    var jwt = getJwt();
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;
    var init = { method: method, headers: headers };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    return fetch(buildUrl(path), init).then(function (resp) {
      if (resp.status === 401 && method !== 'POST' && path !== '/vapt-vendor/invitations/accept') {
        // Force re-auth on 401 from anything except the public accept endpoint
        try { localStorage.removeItem(SESSION_KEY); } catch (_e) {}
        window.location.href = 'vapt-portal-login.html';
        throw new Error('Session expired.');
      }
      if (!resp.ok) return parseError(resp);
      if (resp.status === 204) return null;
      return resp.json();
    });
  }

  function multipartFetch(method, path, formData) {
    var headers = { 'Accept': 'application/json' };
    var jwt = getJwt();
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;
    return fetch(buildUrl(path), {
      method: method,
      headers: headers,
      body: formData,
    }).then(function (resp) {
      if (resp.status === 401) {
        try { localStorage.removeItem(SESSION_KEY); } catch (_e) {}
        window.location.href = 'vapt-portal-login.html';
        throw new Error('Session expired.');
      }
      if (!resp.ok) return parseError(resp);
      return resp.json();
    });
  }

  // ── Public API ────────────────────────────────────────────────────

  function acceptInvitation(token) {
    return jsonFetch('POST', '/vapt-vendor/invitations/accept', { token: token });
  }

  function getProfile() {
    return jsonFetch('GET', '/vapt-vendor/profile');
  }

  function listSubmissions(statusFilter) {
    var path = '/vapt-vendor/submissions';
    if (statusFilter) path += '?sub_status=' + encodeURIComponent(statusFilter);
    return jsonFetch('GET', path);
  }

  function getSubmission(id) {
    return jsonFetch('GET', '/vapt-vendor/submissions/' + encodeURIComponent(id));
  }

  function submitFinding(formData) {
    return multipartFetch('POST', '/vapt-vendor/submissions', formData);
  }

  function submitRetestResponse(submissionId, formData) {
    return multipartFetch(
      'POST',
      '/vapt-vendor/submissions/' + encodeURIComponent(submissionId) +
      '/retest-response',
      formData
    );
  }

  function listNotifications() {
    return jsonFetch('GET', '/vapt-vendor/notifications');
  }

  window.VaptPortalApi = {
    SESSION_KEY: SESSION_KEY,
    acceptInvitation: acceptInvitation,
    getProfile: getProfile,
    listSubmissions: listSubmissions,
    getSubmission: getSubmission,
    submitFinding: submitFinding,
    submitRetestResponse: submitRetestResponse,
    listNotifications: listNotifications,
  };
})();
