/**
 * URIP — Unified Application Shell (Wave A)
 *
 * Renders the 10-domain cockpit sidebar + topbar + page-action row on every
 * authenticated page. Pages opt in by:
 *   1. Adding class="urip-app" on <body>
 *   2. Wrapping content as <div id="app-shell" data-page="risk-overview"></div>
 *   3. Calling URIP.shell.mount({ page, title, breadcrumb, actions })
 *
 * Mirrors MASTER_BLUEPRINT §6.5 sidebar taxonomy. Pure DOM (no innerHTML).
 *
 * Depends on: api.js, theming.js, auth.js
 */
(function () {
  'use strict';

  var URIP = window.URIP || {};
  var SIDEBAR_KEY = 'urip_app_sidebar_collapsed';

  // ---------------------------------------------------------------------------
  // 10-domain sidebar taxonomy (per MASTER_BLUEPRINT §6.5)
  // ---------------------------------------------------------------------------
  var NAV = [
    {
      title: 'Risk Center',
      items: [
        { id: 'dashboard',      label: 'Dashboard',      icon: 'fa-th-large',      href: 'dashboard.html' },
        { id: 'risk-overview',  label: 'Risk Overview',  icon: 'fa-chart-pie',     href: 'risk-overview.html' },
        { id: 'risk-register',  label: 'Risk Register',  icon: 'fa-list-check',    href: 'risk-register.html' },
        { id: 'threat-map',     label: 'Threat Intel',   icon: 'fa-globe',         href: 'threat-map.html' },
        { id: 'remediation',    label: 'Remediation',    icon: 'fa-tasks',         href: 'remediation-tracker.html' },
        { id: 'acceptance',     label: 'Acceptance',     icon: 'fa-clipboard-check', href: 'acceptance-workflow.html' }
      ]
    },
    {
      title: 'Domains',
      items: [
        { id: 'endpoint',   label: 'Endpoint',       icon: 'fa-shield-halved',   href: 'risk-register.html?domain=endpoint',  emoji: '🛡️' },
        { id: 'identity',   label: 'Identity',       icon: 'fa-key',             href: 'risk-register.html?domain=identity',  emoji: '🔑' },
        { id: 'network',    label: 'Network',        icon: 'fa-network-wired',   href: 'risk-register.html?domain=network',   emoji: '🌐' },
        { id: 'cloud',      label: 'Cloud Security', icon: 'fa-cloud',           href: 'cspm-dashboard.html',                  emoji: '☁️' },
        { id: 'email',      label: 'Email & Collab', icon: 'fa-envelope',        href: 'risk-register.html?domain=email',     emoji: '📧' },
        { id: 'mobile',     label: 'Mobile',         icon: 'fa-mobile-screen',   href: 'risk-register.html?domain=mobile',    emoji: '📱' },
        { id: 'ot',         label: 'OT Security',    icon: 'fa-industry',        href: 'risk-register.html?domain=ot',        emoji: '🏭' },
        { id: 'external',   label: 'External Threat',icon: 'fa-earth-asia',      href: 'threat-map.html?domain=external',     emoji: '🌍' }
      ]
    },
    {
      title: 'Strategic Modules',
      items: [
        { id: 'cspm-dashboard',     label: 'CSPM',              icon: 'fa-cloud-arrow-up',  href: 'cspm-dashboard.html' },
        { id: 'dspm-dashboard',     label: 'DSPM',              icon: 'fa-database',        href: 'dspm-dashboard.html' },
        { id: 'ai-security',        label: 'AI Security',       icon: 'fa-robot',           href: 'ai-security-dashboard.html' },
        { id: 'ztna',               label: 'ZTNA',              icon: 'fa-user-lock',       href: 'ztna-dashboard.html' },
        { id: 'attack-path',        label: 'Attack Path',       icon: 'fa-diagram-project', href: 'attack-path.html' },
        { id: 'risk-quantification',label: 'Risk Quant',        icon: 'fa-chart-line',      href: 'risk-quantification.html' }
      ]
    },
    {
      title: 'Compliance',
      items: [
        { id: 'compliance', label: 'Compliance',     icon: 'fa-clipboard-list',  href: '../compliance/frontend/index.html', extLink: true }
      ]
    },
    {
      title: 'Operations',
      items: [
        { id: 'workflow',         label: 'Workflow Auto',  icon: 'fa-robot',           href: 'remediation-tracker.html?tab=auto' },
        { id: 'audit-log',        label: 'Audit Log',      icon: 'fa-clock-rotate-left', href: 'audit-log.html' },
        { id: 'reports',          label: 'Reports',        icon: 'fa-file-lines',      href: 'reports.html' },
        { id: 'asset-inventory',  label: 'Asset Inventory',icon: 'fa-boxes-stacked',   href: 'asset-inventory.html' }
      ]
    },
    {
      title: 'Configuration',
      items: [
        { id: 'tool-catalog',     label: 'Tool Catalog',  icon: 'fa-puzzle-piece', href: 'tool-catalog.html' },
        { id: 'connector-status', label: 'Connectors',    icon: 'fa-heart-pulse',  href: 'connector-status.html' },
        { id: 'connector-wizard', label: 'Connector Wizard', icon: 'fa-wand-magic-sparkles', href: 'connector-wizard.html' },
        { id: 'settings',         label: 'Settings',      icon: 'fa-gear',         href: 'settings.html' }
      ]
    },
    {
      title: 'Administration',
      items: [
        { id: 'admin-tenants',    label: 'Tenants',       icon: 'fa-building',     href: 'admin-tenants.html', superAdminOnly: true },
        { id: 'admin-modules',    label: 'Modules',       icon: 'fa-cubes',        href: 'admin-modules.html' },
        { id: 'admin-scoring',    label: 'Scoring Weights', icon: 'fa-sliders',    href: 'admin-scoring.html' },
        { id: 'admin-vapt',       label: 'VAPT Vendors',  icon: 'fa-user-shield',  href: 'admin-vapt.html' }
      ]
    }
  ];

  // ---------------------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------------------
  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }
  function fa(name) {
    var i = document.createElement('i');
    i.className = 'fas ' + name;
    return i;
  }

  // ---------------------------------------------------------------------------
  // Sidebar
  // ---------------------------------------------------------------------------
  function buildSidebar(activePage, user) {
    var aside = el('aside', 'app-sidebar');
    aside.setAttribute('aria-label', 'Primary navigation');

    // Brand
    var brand = el('a', 'app-sidebar-brand');
    brand.href = 'risk-overview.html';
    brand.setAttribute('aria-label', 'Go to Risk Overview');

    var b = (URIP.branding) || {};
    var logo = el('div', 'app-sidebar-logo');
    var initial = (b.app_name || 'URIP').trim().charAt(0).toUpperCase();
    logo.textContent = initial;
    brand.appendChild(logo);

    var brandText = el('div');
    brandText.appendChild(el('div', 'app-sidebar-name', b.app_name || 'URIP'));
    brandText.appendChild(el('div', 'app-sidebar-tag', b.app_tagline || 'Risk Cockpit'));
    brand.appendChild(brandText);
    aside.appendChild(brand);

    // Scrollable nav
    var scroll = el('div', 'app-sidebar-scroll');

    var isSuperAdmin = user && user.role && /super[-_ ]?admin/i.test(user.role);

    NAV.forEach(function (section) {
      var sec = el('div', 'app-side-section');
      sec.appendChild(el('div', 'app-side-section-title', section.title));

      section.items.forEach(function (item) {
        if (item.superAdminOnly && !isSuperAdmin) return;

        var link = el('a', 'app-side-link');
        link.href = item.href;
        link.setAttribute('data-page', item.id);
        link.setAttribute('title', item.label);
        if (item.id === activePage) link.classList.add('is-active');

        var icon = el('span', 'app-side-icon');
        icon.appendChild(fa(item.icon));
        link.appendChild(icon);

        link.appendChild(el('span', 'app-side-text', item.label));
        sec.appendChild(link);
      });

      scroll.appendChild(sec);
    });

    aside.appendChild(scroll);

    // Footer
    var foot = el('div', 'app-sidebar-foot');
    foot.appendChild(el('span', null, 'URIP v1.0'));
    var collapseBtn = el('button', 'app-sidebar-collapse-btn');
    collapseBtn.setAttribute('aria-label', 'Collapse sidebar');
    collapseBtn.appendChild(fa('fa-chevron-left'));
    collapseBtn.addEventListener('click', toggleCollapse);
    foot.appendChild(collapseBtn);
    aside.appendChild(foot);

    return aside;
  }

  function toggleCollapse() {
    var shell = document.querySelector('.app-shell');
    if (!shell) return;
    shell.classList.toggle('is-collapsed');
    var collapsed = shell.classList.contains('is-collapsed');
    try { localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0'); } catch (_e) {}
    var btn = shell.querySelector('.app-sidebar-collapse-btn i');
    if (btn) btn.className = 'fas ' + (collapsed ? 'fa-chevron-right' : 'fa-chevron-left');
  }

  // ---------------------------------------------------------------------------
  // Topbar
  // ---------------------------------------------------------------------------
  function buildTopbar(opts, user) {
    var bar = el('header', 'app-topbar');
    bar.setAttribute('role', 'banner');

    // Mobile sidebar toggle
    var mobileBtn = el('button', 'app-iconbtn');
    mobileBtn.setAttribute('aria-label', 'Toggle navigation');
    mobileBtn.appendChild(fa('fa-bars'));
    mobileBtn.style.display = 'none';
    mobileBtn.classList.add('app-mobile-only');
    mobileBtn.addEventListener('click', function () {
      var aside = document.querySelector('.app-sidebar');
      if (aside) aside.classList.toggle('is-mobile-open');
    });

    var left = el('div', 'app-topbar-left');
    left.appendChild(mobileBtn);

    // Title + breadcrumb
    var titleBox = el('div');
    titleBox.style.display = 'flex';
    titleBox.style.flexDirection = 'column';
    if (opts.breadcrumb) {
      titleBox.appendChild(el('div', 'crumbs', opts.breadcrumb));
    }
    var pageTitle = el('div');
    pageTitle.style.fontSize = '14px';
    pageTitle.style.fontWeight = '600';
    pageTitle.style.color = 'var(--u-fg)';
    pageTitle.textContent = opts.title || '';
    titleBox.appendChild(pageTitle);
    left.appendChild(titleBox);
    bar.appendChild(left);

    // Search
    var search = el('div', 'app-topbar-search');
    search.appendChild(fa('fa-magnifying-glass'));
    var searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = 'Search risks, connectors, controls…';
    searchInput.setAttribute('aria-label', 'Global search');
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.location.href = 'global-search.html?q=' + encodeURIComponent(searchInput.value.trim());
      }
    });
    search.appendChild(searchInput);
    bar.appendChild(search);

    // Right actions
    var right = el('div', 'app-topbar-right');

    // Clock
    var clock = el('div', 'app-topbar-clock');
    bar.appendChild(right);
    right.appendChild(clock);
    function tickClock() {
      var d = new Date();
      var hh = String(d.getHours()).padStart(2,'0');
      var mm = String(d.getMinutes()).padStart(2,'0');
      var dd = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      clock.textContent = dd + '  ' + hh + ':' + mm;
    }
    tickClock();
    setInterval(tickClock, 60000);

    // Tenant pill
    var brand = (URIP.branding) || {};
    var tenantPill = el('div', 'app-tenant-pill');
    tenantPill.appendChild(el('span', 'dot'));
    tenantPill.appendChild(document.createTextNode(brand.app_name || (user && user.tenant_name) || 'Tenant'));
    tenantPill.setAttribute('title', 'Switch tenant');
    var isSuperAdmin = user && user.role && /super[-_ ]?admin/i.test(user.role);
    if (isSuperAdmin) {
      tenantPill.style.cursor = 'pointer';
      tenantPill.appendChild(fa('fa-chevron-down'));
      tenantPill.addEventListener('click', function () {
        window.location.href = 'admin-tenants.html';
      });
    }
    right.appendChild(tenantPill);

    // Notifications
    var notifWrap = el('div');
    notifWrap.style.position = 'relative';
    var notifBtn = el('button', 'app-iconbtn');
    notifBtn.setAttribute('aria-label', 'Notifications');
    notifBtn.appendChild(fa('fa-bell'));
    var dot = el('span', 'app-iconbtn-dot');
    dot.style.display = 'none';
    notifBtn.appendChild(dot);
    notifWrap.appendChild(notifBtn);

    var notifDD = el('div', 'app-dropdown');
    notifDD.style.minWidth = '320px';
    var notifHeader = el('div');
    notifHeader.style.padding = '10px 12px';
    notifHeader.style.fontSize = '11px';
    notifHeader.style.fontWeight = '700';
    notifHeader.style.color = 'var(--u-fg-3)';
    notifHeader.style.textTransform = 'uppercase';
    notifHeader.style.letterSpacing = '.08em';
    notifHeader.textContent = 'Recent activity';
    notifDD.appendChild(notifHeader);

    var notifBody = el('div');
    notifBody.style.maxHeight = '320px';
    notifBody.style.overflowY = 'auto';
    notifBody.appendChild(el('div', 'u-empty', 'No recent notifications.'));
    notifDD.appendChild(notifBody);

    var notifFoot = document.createElement('a');
    notifFoot.className = 'app-dropdown-item';
    notifFoot.style.borderTop = '1px solid var(--u-border)';
    notifFoot.style.justifyContent = 'center';
    notifFoot.textContent = 'View all';
    notifFoot.href = 'notifications.html';
    notifDD.appendChild(notifFoot);

    notifWrap.appendChild(notifDD);

    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      notifDD.classList.toggle('is-open');
      if (notifDD.classList.contains('is-open')) loadNotifications(notifBody, dot);
    });
    right.appendChild(notifWrap);

    // Help
    var helpBtn = el('button', 'app-iconbtn');
    helpBtn.setAttribute('aria-label', 'Help');
    helpBtn.appendChild(fa('fa-circle-question'));
    helpBtn.addEventListener('click', function () {
      window.URIP.showNotification('Help', 'See the inline setup guide on each connector tile, or contact your administrator.', 'info');
    });
    right.appendChild(helpBtn);

    // User menu
    var userWrap = el('div');
    userWrap.style.position = 'relative';

    var userBox = el('div', 'app-user');
    var avatar = el('div', 'app-user-avatar');
    var name = (user && (user.full_name || user.email)) || 'User';
    var role = (user && user.role) || 'member';
    var initials = computeInitials(name);
    avatar.textContent = initials;

    var nameStack = el('div');
    nameStack.appendChild(el('div', 'app-user-name', name));
    nameStack.appendChild(el('div', 'app-user-role', role));

    userBox.appendChild(avatar);
    userBox.appendChild(nameStack);
    userBox.appendChild(fa('fa-chevron-down'));
    userWrap.appendChild(userBox);

    var userDD = el('div', 'app-dropdown');
    var profile = el('a', 'app-dropdown-item');
    profile.href = 'profile.html';
    profile.appendChild(fa('fa-user'));
    profile.appendChild(document.createTextNode('Profile'));
    userDD.appendChild(profile);

    var settings2 = el('a', 'app-dropdown-item');
    settings2.href = 'settings.html';
    settings2.appendChild(fa('fa-gear'));
    settings2.appendChild(document.createTextNode('Settings'));
    userDD.appendChild(settings2);

    userDD.appendChild(el('div', 'app-dropdown-divider'));

    var signOut = el('a', 'app-dropdown-item');
    signOut.href = '#';
    signOut.appendChild(fa('fa-right-from-bracket'));
    signOut.appendChild(document.createTextNode('Sign out'));
    signOut.addEventListener('click', function (e) {
      e.preventDefault();
      if (typeof window.logout === 'function') window.logout();
      else {
        localStorage.removeItem('urip_token');
        localStorage.removeItem('urip_user');
        window.location.href = 'index.html';
      }
    });
    userDD.appendChild(signOut);

    userWrap.appendChild(userDD);
    userBox.addEventListener('click', function (e) {
      e.stopPropagation();
      userDD.classList.toggle('is-open');
    });
    right.appendChild(userWrap);

    // Click outside closes dropdowns
    document.addEventListener('click', function () {
      notifDD.classList.remove('is-open');
      userDD.classList.remove('is-open');
    });

    return bar;
  }

  function computeInitials(name) {
    var parts = (name || '').trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    if (parts.length === 1 && parts[0].length) return parts[0].substring(0, 2).toUpperCase();
    return 'U';
  }

  async function loadNotifications(body, dot) {
    if (!URIP.apiFetch) return;
    body.textContent = '';
    var loading = el('div', 'u-empty', 'Loading…');
    body.appendChild(loading);
    try {
      var data = await URIP.apiFetch('/audit-log?per_page=8', { silent: true });
      body.textContent = '';
      var items = (data && (data.items || data.entries || data)) || [];
      if (!Array.isArray(items)) items = [];
      if (!items.length) {
        body.appendChild(makeEmpty('fa-bell-slash', 'No recent notifications', 'You\'ll see logins, risks, and ticket events here.'));
        dot.style.display = 'none';
        return;
      }
      dot.style.display = '';
      items.slice(0, 8).forEach(function (it) {
        var row = el('div');
        row.style.padding = '8px 12px';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.appendChild(el('div', null, (it.action || it.event_type || it.message || 'Activity')));
        var meta = el('div');
        meta.style.fontSize = '11px';
        meta.style.color = 'var(--u-fg-3)';
        var when = it.timestamp || it.created_at || '';
        meta.textContent = (it.user_email || it.actor || '') + (when ? ' • ' + relTime(when) : '');
        row.appendChild(meta);
        body.appendChild(row);
      });
    } catch (_e) {
      body.textContent = '';
      body.appendChild(makeEmpty('fa-triangle-exclamation', 'Could not load notifications', 'Check your connection or try again later.'));
    }
  }

  // ---------------------------------------------------------------------------
  // Page action row
  // ---------------------------------------------------------------------------
  function buildActionRow(opts) {
    var row = el('div', 'app-action-row');

    // Breadcrumb
    var crumbs = el('div', 'crumbs');
    var b = el('strong', null, 'URIP');
    crumbs.appendChild(b);
    crumbs.appendChild(document.createTextNode(' / ' + (opts.breadcrumb || opts.title || '')));
    row.appendChild(crumbs);

    var spacer = el('div', 'app-action-spacer');
    row.appendChild(spacer);

    // Page actions (rendered by caller)
    if (Array.isArray(opts.actions)) {
      opts.actions.forEach(function (a) {
        var btn = el('button', 'u-btn ' + (a.variant || ''));
        if (a.icon) btn.appendChild(fa(a.icon));
        btn.appendChild(document.createTextNode(a.label));
        if (a.onClick) btn.addEventListener('click', a.onClick);
        if (a.href) btn.addEventListener('click', function () { window.location.href = a.href; });
        row.appendChild(btn);
      });
    }

    return row;
  }

  // ---------------------------------------------------------------------------
  // Mount the shell
  // ---------------------------------------------------------------------------
  function mount(opts) {
    opts = opts || {};
    var container = document.getElementById('app-shell');
    if (!container) {
      console.warn('URIP.shell: no #app-shell element found');
      return;
    }

    // Capture inner content (the page-specific markup) so we can re-insert it
    var children = [];
    while (container.firstChild) children.push(container.removeChild(container.firstChild));

    container.classList.add('app-shell');
    var collapsed = false;
    try { collapsed = localStorage.getItem(SIDEBAR_KEY) === '1'; } catch (_e) {}
    if (collapsed) container.classList.add('is-collapsed');

    var user = (typeof window.getCurrentUser === 'function') ? window.getCurrentUser() : null;
    if (!user) {
      try { user = JSON.parse(localStorage.getItem('urip_user') || 'null'); } catch (_e) { user = null; }
    }

    var page = opts.page || container.getAttribute('data-page');
    var sidebar = buildSidebar(page, user);
    var main = el('div', 'app-main');
    var topbar = buildTopbar(opts, user);
    main.appendChild(topbar);
    main.appendChild(buildActionRow(opts));

    var content = el('main', 'app-content');
    content.id = 'app-content';
    children.forEach(function (c) { content.appendChild(c); });
    main.appendChild(content);

    container.appendChild(sidebar);
    container.appendChild(main);
  }

  // Helpers exposed to pages
  function makeEmpty(icon, title, body) {
    var n = el('div', 'u-empty');
    var ic = el('div', 'icon');
    ic.appendChild(fa(icon || 'fa-folder-open'));
    n.appendChild(ic);
    if (title) n.appendChild(el('div', 'title', title));
    if (body) n.appendChild(el('div', 'body', body));
    return n;
  }

  function relTime(iso) {
    if (!iso) return '';
    var t = Date.parse(iso);
    if (isNaN(t)) return iso;
    var d = Math.floor((Date.now() - t) / 1000);
    if (d < 60) return d + 's ago';
    if (d < 3600) return Math.floor(d/60) + 'm ago';
    if (d < 86400) return Math.floor(d/3600) + 'h ago';
    return Math.floor(d/86400) + 'd ago';
  }

  function severityBadge(sev) {
    sev = (sev || 'info').toString().toLowerCase();
    var b = el('span', 'u-badge is-' + (['critical','high','medium','low','info'].indexOf(sev) >= 0 ? sev : 'info'));
    b.textContent = sev;
    return b;
  }
  function lifecyclePill(status) {
    status = (status || 'roadmap').toString().toLowerCase();
    var p = el('span', 'u-pill is-' + (['live','building','simulated','roadmap'].indexOf(status) >= 0 ? status : 'roadmap'));
    p.textContent = status;
    return p;
  }

  URIP.shell = {
    mount: mount,
    NAV: NAV,
    el: el,
    fa: fa,
    makeEmpty: makeEmpty,
    relTime: relTime,
    severityBadge: severityBadge,
    lifecyclePill: lifecyclePill,
    computeInitials: computeInitials
  };
  window.URIP = URIP;
})();
