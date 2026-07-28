/**
 * StayHub Design System – Main JavaScript
 * Reusable UI components: Toast, Modal, Dropdown, Dark Mode, Navigation
 */

(function() {
  'use strict';

  // ===================== TOAST SYSTEM =====================
  const Toast = {
    show: function(message, type, duration) {
      type = type || 'info';
      duration = duration || 3200;

      // Remove existing toast
      var existing = document.querySelector('.toast');
      if (existing) existing.remove();

      var toast = document.createElement('div');
      toast.className = 'toast toast-' + type + ' toast-visible';
      toast.textContent = message;
      document.body.appendChild(toast);

      setTimeout(function() {
        toast.classList.remove('toast-visible');
        setTimeout(function() { toast.remove(); }, 300);
      }, duration);
    },

    success: function(msg) { this.show(msg, 'success'); },
    error: function(msg) { this.show(msg, 'error'); },
    warning: function(msg) { this.show(msg, 'warning'); },
    info: function(msg) { this.show(msg, 'info'); }
  };

  // ===================== MODAL SYSTEM =====================
  const Modal = {
    open: function(options) {
      var overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML =
        '<div class="modal">' +
          '<h3 class="modal-title">' + (options.title || '') + '</h3>' +
          '<div class="modal-body">' + (options.body || '') + '</div>' +
          '<div class="modal-actions">' +
            (options.cancelText
              ? '<button class="btn btn-ghost modal-cancel">' + options.cancelText + '</button>'
              : '') +
            '<button class="btn btn-primary modal-confirm">' + (options.confirmText || 'Confirm') + '</button>' +
          '</div>' +
        '</div>';

      document.body.appendChild(overlay);
      requestAnimationFrame(function() {
        overlay.classList.add('active');
      });

      var promise = new Promise(function(resolve) {
        overlay.querySelector('.modal-confirm').addEventListener('click', function() {
          Modal.close(overlay);
          resolve(true);
        });
        var cancelBtn = overlay.querySelector('.modal-cancel');
        if (cancelBtn) {
          cancelBtn.addEventListener('click', function() {
            Modal.close(overlay);
            resolve(false);
          });
        }
        overlay.addEventListener('click', function(e) {
          if (e.target === overlay) {
            Modal.close(overlay);
            resolve(false);
          }
        });
      });

      return promise;
    },

    close: function(overlay) {
      overlay.classList.remove('active');
      setTimeout(function() { overlay.remove(); }, 200);
    }
  };

  // ===================== DARK MODE TOGGLE =====================
  const DarkMode = {
    init: function() {
      var saved = localStorage.getItem('stayhub-dark-mode');
      var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

      if (saved === 'true' || (saved === null && prefersDark)) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }

      // Listen for toggle changes
      document.addEventListener('change', function(e) {
        if (e.target.matches('.dark-mode-toggle')) {
          DarkMode.toggle();
        }
      });
    },

    toggle: function() {
      var isDark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('stayhub-dark-mode', isDark);
      // Dispatch custom event for other components
      document.dispatchEvent(new CustomEvent('darkmodechange', { detail: { dark: isDark } }));
    },

    isDark: function() {
      return document.documentElement.classList.contains('dark');
    },

    set: function(dark) {
      if (dark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      localStorage.setItem('stayhub-dark-mode', dark);
    }
  };

  // ===================== DROPDOWN =====================
  const Dropdown = {
    init: function() {
      document.addEventListener('click', function(e) {
        var toggle = e.target.closest('[data-dropdown-toggle]');
        if (toggle) {
          e.preventDefault();
          var menuId = toggle.getAttribute('data-dropdown-toggle');
          var menu = document.getElementById(menuId);
          if (menu) {
            menu.classList.toggle('active');
          }
          return;
        }

        // Close all dropdowns when clicking outside
        document.querySelectorAll('.dropdown-menu.active').forEach(function(menu) {
          var toggle = document.querySelector('[data-dropdown-toggle="' + menu.id + '"]');
          if (!toggle || !toggle.contains(e.target)) {
            menu.classList.remove('active');
          }
        });
      });
    }
  };

  // ===================== BOTTOM NAVIGATION =====================
  const BottomNav = {
    init: function() {
      var navLinks = document.querySelectorAll('.nav-link');
      var currentPath = window.location.pathname;

      navLinks.forEach(function(link) {
        var href = link.getAttribute('href');
        var icon = link.querySelector('.material-symbols-outlined');
        if (href && currentPath === href) {
          link.classList.add('active');
          if (icon) icon.style.setProperty('font-variation-settings', '"FILL" 1');
        }
      });
    }
  };

  // ===================== HEADER SCROLL SHADOW =====================
  const HeaderScroll = {
    init: function() {
      var header = document.querySelector('header.fixed');
      if (!header) return;
      window.addEventListener('scroll', function() {
        if (window.scrollY > 16) {
          header.classList.add('shadow-md');
        } else {
          header.classList.remove('shadow-md');
        }
      }, { passive: true });
    }
  };

  // ===================== SEARCH HANDLER =====================
  const SearchHandler = {
    init: function() {
      var searchInput = document.getElementById('search-input');
      var searchButton = document.getElementById('search-button');
      if (!searchInput || !searchButton) return;

      var doSearch = function() {
        var v = searchInput.value.trim();
        if (v) {
          window.location.href = searchButton.getAttribute('data-search-url') || '/explore?q=' + encodeURIComponent(v);
        }
      };
      searchButton.addEventListener('click', doSearch);
      searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') doSearch();
      });
    }
  };

  // ===================== DATE PICKER STYLING =====================
  // Fix date input styling by setting min date
  document.addEventListener('DOMContentLoaded', function() {
    var dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(function(input) {
      if (!input.getAttribute('min')) {
        var today = new Date();
        input.setAttribute('min', today.toISOString().split('T')[0]);
      }
    });
  });

  // ===================== INIT ON DOM READY =====================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    DarkMode.init();
    Dropdown.init();
    BottomNav.init();
    HeaderScroll.init();
    SearchHandler.init();
  }

  // Expose to global scope for inline usage
  window.StayHub = {
    Toast: Toast,
    Modal: Modal,
    DarkMode: DarkMode,
    Dropdown: Dropdown
  };

})();