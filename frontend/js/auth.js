/**
 * URIP - Authentication (Login / Logout / Auth Guard)
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  /**
   * Handle login form submission.
   * Calls POST /api/auth/login, stores token + user, redirects to dashboard.
   *
   * @param {Event} event - form submit event
   */
  async function handleLogin(event) {
    event.preventDefault();

    var form = event.target;
    var emailInput = form.querySelector('input[type="email"]');
    var passwordInput = form.querySelector('input[type="password"]');
    var btn = form.querySelector('.login-btn') || form.querySelector('button[type="submit"]');

    if (!emailInput || !passwordInput) {
      return;
    }

    var email = emailInput.value.trim();
    var password = passwordInput.value;

    if (!email || !password) {
      window.URIP.showNotification('Validation Error', 'Please enter both email and password.', 'error');
      return;
    }

    // Save original button children for restore on error
    var originalChildren = [];
    while (btn.firstChild) {
      originalChildren.push(btn.removeChild(btn.firstChild));
    }

    // Show loading state
    var spinner = document.createElement('i');
    spinner.className = 'fas fa-spinner fa-spin';
    btn.appendChild(spinner);
    btn.appendChild(document.createTextNode(' Authenticating...'));
    btn.disabled = true;

    try {
      var data = await window.URIP.apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email, password: password })
      });

      if (data && data.access_token) {
        localStorage.setItem('urip_token', data.access_token);
        localStorage.setItem('urip_user', JSON.stringify(data.user));
        window.location.href = 'dashboard.html';
      }
    } catch (err) {
      window.URIP.showNotification(
        'Login Failed',
        (err && err.body && err.body.detail) || 'Invalid email or password.',
        'error'
      );
      // Restore original button content
      btn.textContent = '';
      originalChildren.forEach(function (child) { btn.appendChild(child); });
      btn.disabled = false;
    }
  }

  /**
   * Check if user is authenticated.
   * Call on every protected page load.
   * Redirects to index.html if no token found.
   */
  function checkAuth() {
    var token = localStorage.getItem('urip_token');
    if (!token) {
      window.location.href = 'index.html';
    }
  }

  /**
   * Log out: clear localStorage and redirect to login.
   */
  function logout() {
    localStorage.removeItem('urip_token');
    localStorage.removeItem('urip_user');
    window.location.href = 'index.html';
  }

  /**
   * Get current user object from localStorage.
   *
   * @returns {object|null} Parsed user object or null
   */
  function getCurrentUser() {
    var raw = localStorage.getItem('urip_user');
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  // Expose globally
  window.handleLogin = handleLogin;
  window.checkAuth = checkAuth;
  window.logout = logout;
  window.getCurrentUser = getCurrentUser;
})();
