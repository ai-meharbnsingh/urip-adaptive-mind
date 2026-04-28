/**
 * ADVERB COMPLIANCE — Sidebar + Topbar
 *
 * Renders the navy-gradient sidebar with all 11 nav items. No innerHTML —
 * uses createElement only (XSS-safe).
 *
 * Active page is passed as the only argument: renderSidebar('dashboard').
 */
(function () {
  'use strict';

  var NAV_SECTIONS = [
    {
      title: 'Compliance',
      items: [
        { label: 'Dashboard',          href: 'index.html',                icon: 'fa-shield-halved',     page: 'dashboard' },
        { label: 'Frameworks',         href: 'frameworks.html',           icon: 'fa-layer-group',       page: 'frameworks' },
        { label: 'Controls',           href: 'controls.html',             icon: 'fa-list-check',        page: 'controls', badgeAPI: '/controls/runs?status=fail&limit=1' },
        { label: 'Evidence',           href: 'evidence.html',             icon: 'fa-folder-open',       page: 'evidence' },
        { label: 'Policies',           href: 'policies.html',             icon: 'fa-file-signature',    page: 'policies', badgeAPI: '/policies/pending' },
        { label: 'Vendors',            href: 'vendors.html',              icon: 'fa-handshake',         page: 'vendors', badgeAPI: '/vendors/expiring-documents?days=60' },
        { label: 'Reports',            href: 'reports.html',              icon: 'fa-file-pdf',          page: 'reports' }
      ]
    },
    {
      title: 'Admin',
      items: [
        { label: 'Auditor Invitations',href: 'auditor-invitations.html',  icon: 'fa-user-tie',          page: 'auditor-invitations' },
        { label: 'Auditor Activity',   href: 'auditor-activity.html',     icon: 'fa-history',           page: 'auditor-activity' },
        { label: 'Evidence Requests',  href: 'evidence-requests.html',    icon: 'fa-inbox',             page: 'evidence-requests' }
      ]
    },
    {
      title: 'Account',
      items: [
        { label: 'Auditor Portal',     href: 'auditor_portal.html',       icon: 'fa-user-shield',       page: 'auditor-portal' },
        { label: 'Logout',             href: '#',                         icon: 'fa-sign-out-alt',      page: 'logout', isLogout: true }
      ]
    }
  ];

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function faIcon(cls) { var i = document.createElement('i'); i.className = 'fas ' + cls; return i; }

  function renderSidebar(activePage) {
    var sidebar = el('aside', 'sidebar');
    var collapsed = localStorage.getItem('compliance_sidebar_collapsed') === 'true';
    if (collapsed) sidebar.classList.add('collapsed');

    var toggle = el('div', 'sidebar-toggle');
    toggle.appendChild(faIcon('fa-chevron-left'));
    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      var c = sidebar.classList.contains('collapsed');
      localStorage.setItem('compliance_sidebar_collapsed', c ? 'true' : 'false');
      var main = document.querySelector('.main-content');
      if (main) main.style.marginLeft = c ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
      var topbar = document.querySelector('.topbar');
      if (topbar) topbar.style.left = c ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
    });
    sidebar.appendChild(toggle);

    // Header / Logo (branded)
    var brand = (window.COMPLIANCE && window.COMPLIANCE.branding) || {};
    var brandAppName = brand.app_name || 'Adverb Compliance';
    var brandTagline = brand.app_tagline || 'Audit-Ready, Always';

    var header = el('div', 'sidebar-header');
    var logoLink = document.createElement('a');
    logoLink.href = 'index.html';
    logoLink.className = 'sidebar-logo';

    var logoIcon = el('div', 'sidebar-logo-icon');
    if (brand.logo_url && /^https?:\/\//.test(brand.logo_url)) {
      var img = document.createElement('img');
      img.src = brand.logo_url; img.alt = brandAppName + ' logo';
      img.style.cssText = 'max-width:100%;max-height:30px;display:block';
      img.addEventListener('error', function () {
        logoIcon.textContent = '';
        logoIcon.appendChild(faIcon('fa-shield-halved'));
      });
      logoIcon.appendChild(img);
    } else {
      logoIcon.appendChild(faIcon('fa-shield-halved'));
    }
    logoLink.appendChild(logoIcon);

    var logoText = el('div', 'sidebar-logo-text');
    logoText.appendChild(el('div', 'sidebar-logo-title', brandAppName));
    logoText.appendChild(el('div', 'sidebar-logo-subtitle', brandTagline));
    logoLink.appendChild(logoText);
    header.appendChild(logoLink);
    sidebar.appendChild(header);

    // Nav
    var nav = document.createElement('nav');
    nav.className = 'sidebar-nav';

    NAV_SECTIONS.forEach(function (section) {
      var sec = el('div', 'sidebar-nav-section');
      sec.appendChild(el('div', 'sidebar-nav-title', section.title));
      var ul = el('ul', 'sidebar-nav-list');
      section.items.forEach(function (item) {
        var li = el('li', 'sidebar-nav-item');
        li.setAttribute('data-title', item.label);
        var link = document.createElement('a');
        link.className = 'sidebar-nav-link';
        if (item.page === activePage) link.classList.add('active');
        if (item.isLogout) {
          link.href = '#';
          link.addEventListener('click', function (e) {
            e.preventDefault();
            if (typeof window.logout === 'function') window.logout();
          });
        } else {
          link.href = item.href;
        }
        var icon = el('span', 'sidebar-nav-icon');
        icon.appendChild(faIcon(item.icon));
        link.appendChild(icon);
        link.appendChild(el('span', 'sidebar-nav-text', item.label));

        if (item.badgeAPI) {
          var badge = el('span', 'sidebar-nav-badge');
          badge.setAttribute('data-badge-api', item.badgeAPI);
          badge.style.display = 'none';
          link.appendChild(badge);
        }

        li.appendChild(link);
        ul.appendChild(li);
      });
      sec.appendChild(ul);
      nav.appendChild(sec);
    });
    sidebar.appendChild(nav);

    // Footer
    var footer = el('div', 'sidebar-footer');
    footer.appendChild(el('div', 'sidebar-version', 'Adverb Compliance v1.0'));
    sidebar.appendChild(footer);

    var mount = document.getElementById('sidebar-mount');
    if (mount) {
      mount.textContent = '';
      mount.appendChild(sidebar);
    } else {
      var existing = document.querySelector('aside.sidebar');
      if (existing && existing.parentNode) existing.parentNode.replaceChild(sidebar, existing);
    }

    if (collapsed) {
      var main = document.querySelector('.main-content');
      if (main) main.style.marginLeft = 'var(--sidebar-collapsed)';
      var topbar = document.querySelector('.topbar');
      if (topbar) topbar.style.left = 'var(--sidebar-collapsed)';
    }

    loadBadgeCounts();
    renderTopbar();
  }

  function loadBadgeCounts() {
    if (!(window.COMPLIANCE && window.COMPLIANCE.apiFetch)) return;
    var badges = document.querySelectorAll('[data-badge-api]');
    badges.forEach(function (badge) {
      var apiPath = badge.getAttribute('data-badge-api');
      window.COMPLIANCE.apiFetch(apiPath, { silent: true })
        .then(function (data) {
          var count = 0;
          if (data == null) return;
          if (typeof data === 'object' && typeof data.total === 'number') count = data.total;
          else if (Array.isArray(data)) count = data.length;
          else if (typeof data === 'object' && data.items && Array.isArray(data.items)) count = data.total || data.items.length;
          if (count > 0) {
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.style.display = '';
          }
        })
        .catch(function () { /* silent — badge is best-effort */ });
    });
  }

  function renderTopbar() {
    var topbar = document.querySelector('.topbar');
    if (!topbar) return;
    topbar.textContent = '';

    var user = (typeof window.getCurrentUser === 'function') ? window.getCurrentUser() : null;

    var brand = (window.COMPLIANCE && window.COMPLIANCE.branding) || {};
    var orgLabel = brand.app_name || 'Adverb';

    var left = el('div', 'topbar-left');
    var org = el('span', 'org-name');
    org.appendChild(faIcon('fa-building'));
    org.appendChild(document.createTextNode(' ' + orgLabel));
    left.appendChild(org);
    var pill = el('span', 'module-pill', 'Compliance Module');
    left.appendChild(pill);
    topbar.appendChild(left);

    var right = el('div', 'topbar-right');

    // Quick action — invite auditor
    var inviteBtn = document.createElement('a');
    inviteBtn.href = 'auditor-invitations.html';
    inviteBtn.className = 'btn btn-primary btn-sm';
    inviteBtn.appendChild(faIcon('fa-user-plus'));
    inviteBtn.appendChild(document.createTextNode('Invite Auditor'));
    right.appendChild(inviteBtn);

    // User menu
    var menu = el('div', 'user-menu');
    var initials = 'U', fullName = 'Compliance User', roleName = 'Member';
    if (user) {
      fullName = user.full_name || user.email || 'User';
      roleName = (user.role || 'member').toUpperCase();
      var parts = String(fullName).split(/\s+/);
      initials = parts.length >= 2
        ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
        : parts[0].substring(0, 2).toUpperCase();
    }
    menu.appendChild(el('div', 'user-avatar', initials));
    var info = el('div', 'user-info');
    info.appendChild(el('span', 'user-name', fullName));
    info.appendChild(el('span', 'user-role', roleName));
    menu.appendChild(info);
    right.appendChild(menu);

    topbar.appendChild(right);
  }

  window.renderSidebar = renderSidebar;
})();
