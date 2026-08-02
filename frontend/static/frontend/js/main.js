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

  // ===================== API / ERROR HANDLING =====================
  // A small shared wrapper keeps JSON errors consistent across pages while
  // retaining the native fetch API for simple requests.
  const Api = {
    request: async function(url, options) {
      var response;
      try {
        response = await fetch(url, options || {});
      } catch (error) {
        Toast.error('Network error. Please check your connection and try again.');
        throw error;
      }
      var data = {};
      try { data = await response.json(); } catch (ignore) {}
      if (!response.ok) {
        var message = data.detail || data.error || 'Something went wrong. Please try again.';
        Toast.error(message);
        var error = new Error(message);
        error.status = response.status;
        throw error;
      }
      return data;
    }
  };

  // ===================== COOKIE HELPER =====================
  // Single source of truth for reading cookies (used for CSRF tokens).
  function getCookie(name) {
    const cookieValue = `; ${document.cookie}`;
    const parts = cookieValue.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  // ===================== DATA-ATTRIBUTE HANDLERS =====================
  // data-toast="Message"  → show an info toast on click (replaces the old
  // verbose inline document.getElementById('app-toast') snippets everywhere).
  // data-tab-group + data-tab="panel-id" → lightweight tab switching that
  // works on any page without per-page inline scripts.
  const DataAttrs = {
    init: function() {
      document.addEventListener('click', function(e) {
        // data-toast
        var toastEl = e.target.closest('[data-toast]');
        if (toastEl) {
          // Only swallow default behaviour for buttons; anchors keep navigating.
          if (toastEl.tagName !== 'A') e.preventDefault();
          Toast.info(toastEl.getAttribute('data-toast'));
          return;
        }
        // data-tab (only when inside a declared group). Panels are siblings
        // of the group (not descendants), so match them document-wide by id.
        var tabBtn = e.target.closest('[data-tab-group] [data-tab]');
        if (tabBtn) {
          var group = tabBtn.closest('[data-tab-group]');
          var target = tabBtn.getAttribute('data-tab');
          group.querySelectorAll('[data-tab]').forEach(function(btn) {
            var isActive = btn === tabBtn;
            btn.classList.toggle('tab-active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
          });
          document.querySelectorAll('[data-tab-panel]').forEach(function(panel) {
            panel.classList.toggle('hidden', panel.id !== target);
          });
        }
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
    // Dark mode is intentionally disabled for the current StayHub experience.
    document.documentElement.classList.remove('dark');
    Dropdown.init();
    BottomNav.init();
    HeaderScroll.init();
    SearchHandler.init();
    DataAttrs.init();
    document.querySelectorAll('img:not([loading])').forEach(function(img) {
      img.loading = 'lazy';
      img.decoding = 'async';
    });
    document.querySelectorAll('form[data-toast-success]').forEach(function(form) {
      form.addEventListener('submit', function() {
        Toast.success(form.getAttribute('data-toast-success'));
      });
    });
    window.addEventListener('error', function() {
      Toast.error('We could not complete that action. Please try again.');
    });
    window.addEventListener('unhandledrejection', function() {
      Toast.error('We could not complete that action. Please try again.');
    });
  }

  // Expose to global scope for inline usage
  window.StayHub = {
    Toast: Toast,
    Modal: Modal,
    DarkMode: DarkMode,
    Dropdown: Dropdown,
    Api: Api,
    getCookie: getCookie
  };

})();
