/**
 * URIP - Dynamic Sidebar + Topbar Component
 * Renders sidebar navigation and topbar using createElement (NO innerHTML).
 * Depends on: auth.js (getCurrentUser)
 */
(function () {
  'use strict';

  // Navigation definition
  var NAV_SECTIONS = [
    {
      title: 'Main',
      items: [
        { label: 'Dashboard', href: 'dashboard.html', icon: 'fa-th-large', page: 'dashboard' },
        { label: 'Risk Register', href: 'risk-register.html', icon: 'fa-list-alt', page: 'risk-register', badgeAPI: '/risks?per_page=1' },
        { label: 'Acceptance Workflow', href: 'acceptance-workflow.html', icon: 'fa-clipboard-check', page: 'acceptance-workflow', badgeAPI: '/acceptance?status=pending' },
        { label: 'Remediation Tracker', href: 'remediation-tracker.html', icon: 'fa-tasks', page: 'remediation-tracker' },
        { label: 'Threat Map', href: '#', icon: 'fa-globe', page: 'threat-map' }
      ]
    },
    {
      title: 'Analytics',
      items: [
        { label: 'Reports', href: 'reports.html', icon: 'fa-chart-bar', page: 'reports' },
        { label: 'Audit Log', href: 'audit-log.html', icon: 'fa-history', page: 'audit-log' }
      ]
    },
    {
      title: 'Settings',
      items: [
        { label: 'Settings', href: 'settings.html', icon: 'fa-cog', page: 'settings' },
        { label: 'Team', href: '#', icon: 'fa-users', page: 'team' },
        { label: 'Logout', href: '#', icon: 'fa-sign-out-alt', page: 'logout', isLogout: true }
      ]
    }
  ];

  /**
   * Helper: create an element with optional className and textContent.
   */
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  /**
   * Helper: create a Font Awesome icon element.
   */
  function faIcon(iconClass) {
    var i = document.createElement('i');
    i.className = 'fas ' + iconClass;
    return i;
  }

  /**
   * Render the full sidebar and inject into #sidebar-mount or replace existing <aside>.
   *
   * @param {string} activePage - current page identifier (e.g. "dashboard", "risk-register")
   */
  function renderSidebar(activePage) {
    var sidebar = el('aside', 'sidebar');

    // Check collapsed state from localStorage
    var collapsed = localStorage.getItem('urip_sidebar_collapsed') === 'true';
    if (collapsed) {
      sidebar.classList.add('collapsed');
    }

    // Toggle button
    var toggle = el('div', 'sidebar-toggle');
    toggle.appendChild(faIcon('fa-chevron-left'));
    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      var isCollapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem('urip_sidebar_collapsed', isCollapsed ? 'true' : 'false');

      // Adjust main content margin
      var mainContent = document.querySelector('.main-content');
      if (mainContent) {
        mainContent.style.marginLeft = isCollapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
      }
      var topbar = document.querySelector('.topbar');
      if (topbar) {
        topbar.style.left = isCollapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
      }
    });
    sidebar.appendChild(toggle);

    // Header / Logo
    var header = el('div', 'sidebar-header');
    var logoLink = document.createElement('a');
    logoLink.href = 'dashboard.html';
    logoLink.className = 'sidebar-logo';

    var logoIcon = el('div', 'sidebar-logo-icon');
    logoIcon.appendChild(faIcon('fa-shield-alt'));
    logoLink.appendChild(logoIcon);

    var logoText = el('div', 'sidebar-logo-text');

    var logoTitle = el('div', 'sidebar-logo-title');
    logoTitle.appendChild(document.createTextNode('Semantic '));
    var gravitySpan = document.createElement('span');
    gravitySpan.textContent = 'Gravity';
    logoTitle.appendChild(gravitySpan);
    logoText.appendChild(logoTitle);

    var logoSubtitle = el('div', 'sidebar-logo-subtitle', 'Unified Risk Intelligence');
    logoText.appendChild(logoSubtitle);

    logoLink.appendChild(logoText);
    header.appendChild(logoLink);
    sidebar.appendChild(header);

    // Nav
    var nav = document.createElement('nav');
    nav.className = 'sidebar-nav';

    NAV_SECTIONS.forEach(function (section) {
      var sectionDiv = el('div', 'sidebar-nav-section');
      var sectionTitle = el('div', 'sidebar-nav-title', section.title);
      sectionDiv.appendChild(sectionTitle);

      var ul = el('ul', 'sidebar-nav-list');

      section.items.forEach(function (item) {
        var li = el('li', 'sidebar-nav-item');
        li.setAttribute('data-title', item.label);

        var link = document.createElement('a');
        link.className = 'sidebar-nav-link';
        if (item.page === activePage) {
          link.classList.add('active');
        }

        if (item.isLogout) {
          link.href = '#';
          link.addEventListener('click', function (e) {
            e.preventDefault();
            if (typeof window.logout === 'function') {
              window.logout();
            } else {
              localStorage.removeItem('urip_token');
              localStorage.removeItem('urip_user');
              window.location.href = 'index.html';
            }
          });
        } else {
          link.href = item.href;
        }

        var iconSpan = el('span', 'sidebar-nav-icon');
        iconSpan.appendChild(faIcon(item.icon));
        link.appendChild(iconSpan);

        var textSpan = el('span', 'sidebar-nav-text', item.label);
        link.appendChild(textSpan);

        // Badge placeholder (will be loaded from API)
        if (item.badgeAPI) {
          var badge = el('span', 'sidebar-nav-badge');
          badge.setAttribute('data-badge-api', item.badgeAPI);
          badge.style.display = 'none';
          link.appendChild(badge);
        }

        li.appendChild(link);
        ul.appendChild(li);
      });

      sectionDiv.appendChild(ul);
      nav.appendChild(sectionDiv);
    });

    sidebar.appendChild(nav);

    // Footer
    var footer = el('div', 'sidebar-footer');
    var version = el('div', 'sidebar-version', 'URIP v1.0.0 | Build 2026.04');
    footer.appendChild(version);
    sidebar.appendChild(footer);

    // Mount sidebar
    var mount = document.getElementById('sidebar-mount');
    if (mount) {
      mount.textContent = '';
      mount.appendChild(sidebar);
    } else {
      // Replace existing <aside> if present
      var existingAside = document.querySelector('aside.sidebar');
      if (existingAside && existingAside.parentNode) {
        existingAside.parentNode.replaceChild(sidebar, existingAside);
      }
    }

    // Apply collapsed styling to layout elements on init
    if (collapsed) {
      var mainContent = document.querySelector('.main-content');
      if (mainContent) {
        mainContent.style.marginLeft = 'var(--sidebar-collapsed)';
      }
      var topbar = document.querySelector('.topbar');
      if (topbar) {
        topbar.style.left = 'var(--sidebar-collapsed)';
      }
    }

    // Load badge counts from API
    loadBadgeCounts();

    // Render topbar
    renderTopbar();
  }

  /**
   * Load badge counts for nav items that have data-badge-api.
   */
  function loadBadgeCounts() {
    var badges = document.querySelectorAll('[data-badge-api]');
    badges.forEach(function (badge) {
      var apiPath = badge.getAttribute('data-badge-api');
      if (window.URIP && window.URIP.apiFetch) {
        window.URIP.apiFetch(apiPath)
          .then(function (data) {
            var count = 0;
            if (data && typeof data.total === 'number') {
              count = data.total;
            } else if (Array.isArray(data)) {
              count = data.length;
            }
            if (count > 0) {
              badge.textContent = String(count);
              badge.style.display = '';
            }
          })
          .catch(function () {
            // Silently ignore badge load failures
          });
      }
    });
  }

  /**
   * Render the topbar with org name and current user info.
   */
  function renderTopbar() {
    var existingTopbar = document.querySelector('.topbar');
    if (!existingTopbar) return;

    var user = null;
    if (typeof window.getCurrentUser === 'function') {
      user = window.getCurrentUser();
    }
    if (!user) {
      try {
        var raw = localStorage.getItem('urip_user');
        if (raw) user = JSON.parse(raw);
      } catch (_e) { /* ignore */ }
    }

    // Clear existing topbar
    existingTopbar.textContent = '';

    // Left side - org name
    var topbarLeft = el('div', 'topbar-left');
    var orgName = el('span', 'org-name');
    orgName.appendChild(faIcon('fa-building'));
    orgName.appendChild(document.createTextNode(' Royal Enfield'));
    topbarLeft.appendChild(orgName);
    existingTopbar.appendChild(topbarLeft);

    // Right side
    var topbarRight = el('div', 'topbar-right');

    // Notification bell
    var notifBtn = document.createElement('button');
    notifBtn.className = 'notification-btn';
    notifBtn.appendChild(faIcon('fa-bell'));
    var notifBadge = el('span', 'notification-badge');
    notifBtn.appendChild(notifBadge);
    topbarRight.appendChild(notifBtn);

    // User menu
    var userMenu = el('div', 'user-menu');

    var initials = 'U';
    var fullName = 'User';
    var roleName = 'Member';
    if (user) {
      fullName = user.full_name || user.email || 'User';
      roleName = (user.role || 'member').toUpperCase();
      var nameParts = fullName.split(' ');
      if (nameParts.length >= 2) {
        initials = (nameParts[0][0] + nameParts[nameParts.length - 1][0]).toUpperCase();
      } else if (nameParts.length === 1) {
        initials = nameParts[0].substring(0, 2).toUpperCase();
      }
    }

    var avatar = el('div', 'user-avatar', initials);
    userMenu.appendChild(avatar);

    var userInfo = el('div', 'user-info');
    var userName = el('span', 'user-name', fullName);
    var userRole = el('span', 'user-role', roleName);
    userInfo.appendChild(userName);
    userInfo.appendChild(userRole);
    userMenu.appendChild(userInfo);

    var chevron = faIcon('fa-chevron-down');
    chevron.className += ' text-gray-400 text-xs';
    userMenu.appendChild(chevron);

    topbarRight.appendChild(userMenu);
    existingTopbar.appendChild(topbarRight);
  }

  // Expose
  window.renderSidebar = renderSidebar;
})();
