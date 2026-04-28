/**
 * URIP - Sidebar Navigation JavaScript
 * Semantic Gravity - Unified Risk Intelligence Platform
 */

// Initialize sidebar functionality
document.addEventListener('DOMContentLoaded', function() {
  initializeSidebar();
  initializeMobileMenu();
  setActiveNavItem();
});

/**
 * Initialize sidebar toggle functionality
 */
function initializeSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const toggleBtn = document.querySelector('.sidebar-toggle');
  const mainContent = document.querySelector('.main-content');
  const topbar = document.querySelector('.topbar');
  
  if (!toggleBtn || !sidebar) return;
  
  // Check for saved state
  const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  if (isCollapsed) {
    sidebar.classList.add('collapsed');
    updateLayoutForSidebar(true);
  }
  
  toggleBtn.addEventListener('click', function() {
    const isNowCollapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebarCollapsed', isNowCollapsed);
    updateLayoutForSidebar(isNowCollapsed);
  });
}

/**
 * Update layout elements when sidebar state changes
 */
function updateLayoutForSidebar(collapsed) {
  const mainContent = document.querySelector('.main-content');
  const topbar = document.querySelector('.topbar');
  
  if (collapsed) {
    if (mainContent) mainContent.style.marginLeft = 'var(--sidebar-collapsed)';
    if (topbar) topbar.style.left = 'var(--sidebar-collapsed)';
  } else {
    if (mainContent) mainContent.style.marginLeft = 'var(--sidebar-width)';
    if (topbar) topbar.style.left = 'var(--sidebar-width)';
  }
}

/**
 * Initialize mobile menu functionality
 */
function initializeMobileMenu() {
  const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.createElement('div');
  
  overlay.className = 'sidebar-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 150;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
  `;
  
  document.body.appendChild(overlay);
  
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', function() {
      sidebar.classList.toggle('mobile-open');
      overlay.style.opacity = sidebar.classList.contains('mobile-open') ? '1' : '0';
      overlay.style.visibility = sidebar.classList.contains('mobile-open') ? 'visible' : 'hidden';
    });
  }
  
  overlay.addEventListener('click', function() {
    sidebar.classList.remove('mobile-open');
    overlay.style.opacity = '0';
    overlay.style.visibility = 'hidden';
  });
}

/**
 * Set active state on current page's navigation item
 */
function setActiveNavItem() {
  const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
  const navLinks = document.querySelectorAll('.sidebar-nav-link');
  
  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'dashboard.html')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/**
 * Handle window resize
 */
let resizeTimer;
window.addEventListener('resize', function() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(function() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth <= 768 && sidebar) {
      sidebar.classList.add('collapsed');
    }
  }, 250);
});

/**
 * Add hover tooltips for collapsed sidebar
 */
function initializeSidebarTooltips() {
  const navItems = document.querySelectorAll('.sidebar-nav-item');
  
  navItems.forEach(item => {
    const link = item.querySelector('.sidebar-nav-link');
    const text = item.querySelector('.sidebar-nav-text');
    
    if (link && text) {
      item.setAttribute('data-title', text.textContent);
    }
  });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', initializeSidebarTooltips);
