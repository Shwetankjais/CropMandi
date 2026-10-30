/**
 * CropMandi AI — Language Switcher Component
 *
 * This script builds and manages the language-switcher dropdown
 * in the top navigation bar and login page.
 *
 * It expects CropMandiI18n to be loaded first (i18n.js).
 *
 * The HTML should contain an element with id="lang-switcher-mount"
 * where the component will be injected.
 *
 * Alternatively, call CropMandiLangSwitcher.mount(containerEl)
 * to inject into any element.
 */
(function (global) {
  "use strict";

  /* ─────────────────────────────────────────────
     Build the switcher HTML string
  ───────────────────────────────────────────── */
  function _buildHTML() {
    var langs = [
      { code: "en", label: "English",  native: "English" },
      { code: "hi", label: "Hindi",    native: "हिंदी" },
      { code: "kn", label: "Kannada",  native: "ಕನ್ನಡ" }
    ];

    var optionsHTML = langs.map(function (lang) {
      var isActive = (global.CropMandiI18n && global.CropMandiI18n.getLanguage() === lang.code);
      return (
        '<button type="button" ' +
          'class="lang-option' + (isActive ? ' lang-option--active' : '') + '" ' +
          'data-lang="' + lang.code + '" ' +
          'role="option" ' +
          'aria-checked="' + (isActive ? 'true' : 'false') + '" ' +
          'tabindex="0">' +
          '<span class="lang-option__native">' + lang.native + '</span>' +
          (isActive ? '<span class="lang-option__check" aria-hidden="true">✓</span>' : '') +
        '</button>'
      );
    }).join("");

    var currentMeta = (global.CropMandiI18n && global.CropMandiI18n.langMeta)
      ? global.CropMandiI18n.langMeta[global.CropMandiI18n.getLanguage()]
      : { label: "English" };

    return (
      '<div class="lang-switcher" id="lang-switcher" role="combobox" ' +
          'aria-haspopup="listbox" aria-expanded="false" aria-label="Select language">' +
        '<button type="button" class="lang-switcher__btn" ' +
            'id="lang-switcher-btn" ' +
            'aria-controls="lang-switcher-dropdown" ' +
            'aria-expanded="false">' +
          '<svg class="lang-switcher__icon" viewBox="0 0 24 24" fill="none" ' +
              'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
              'stroke-linejoin="round" aria-hidden="true">' +
            '<circle cx="12" cy="12" r="10"/>' +
            '<line x1="2" y1="12" x2="22" y2="12"/>' +
            '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 ' +
                '15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>' +
          '</svg>' +
          '<span class="lang-current-label">' + currentMeta.label + '</span>' +
          '<svg class="lang-switcher__chevron" viewBox="0 0 24 24" fill="none" ' +
              'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" ' +
              'stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M6 9l6 6 6-6"/>' +
          '</svg>' +
        '</button>' +
        '<div class="lang-switcher__dropdown" id="lang-switcher-dropdown" ' +
            'role="listbox" aria-label="Language options">' +
          '<div class="lang-switcher__dropdown-header">Select Language</div>' +
          optionsHTML +
        '</div>' +
      '</div>'
    );
  }

  /* ─────────────────────────────────────────────
     Wire up events after mounting
  ───────────────────────────────────────────── */
  function _wireEvents(container) {
    var switcher = container.querySelector("#lang-switcher");
    var btn = container.querySelector("#lang-switcher-btn");
    var dropdown = container.querySelector("#lang-switcher-dropdown");

    if (!switcher || !btn || !dropdown) return;

    // Toggle open/close
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var isOpen = switcher.getAttribute("aria-expanded") === "true";
      _closeAll();
      if (!isOpen) {
        switcher.setAttribute("aria-expanded", "true");
        btn.setAttribute("aria-expanded", "true");
        dropdown.classList.add("lang-switcher__dropdown--open");
        // Focus first option
        var first = dropdown.querySelector(".lang-option");
        if (first) first.focus();
      }
    });

    // Language option click
    var options = dropdown.querySelectorAll(".lang-option");
    for (var i = 0; i < options.length; i++) {
      (function (opt) {
        opt.addEventListener("click", function () {
          var lang = opt.getAttribute("data-lang");
          if (lang && global.CropMandiI18n) {
            global.CropMandiI18n.setLanguage(lang);
          }
          _closeAll();
          btn.focus();
        });

        // Keyboard: Enter or Space selects; Escape closes
        opt.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            opt.click();
          } else if (e.key === "Escape") {
            _closeAll();
            btn.focus();
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            var next = opt.nextElementSibling;
            if (next && next.classList.contains("lang-option")) next.focus();
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            var prev = opt.previousElementSibling;
            if (prev && prev.classList.contains("lang-option")) {
              prev.focus();
            } else {
              btn.focus();
            }
          }
        });
      })(options[i]);
    }

    // Keyboard: Escape closes from button
    btn.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        _closeAll();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        switcher.setAttribute("aria-expanded", "true");
        btn.setAttribute("aria-expanded", "true");
        dropdown.classList.add("lang-switcher__dropdown--open");
        var first = dropdown.querySelector(".lang-option");
        if (first) first.focus();
      }
    });
  }

  /* ─────────────────────────────────────────────
     Close all open switchers on the page
  ───────────────────────────────────────────── */
  function _closeAll() {
    var switchers = document.querySelectorAll("#lang-switcher");
    var dropdowns = document.querySelectorAll("#lang-switcher-dropdown");
    var btns = document.querySelectorAll("#lang-switcher-btn");

    for (var i = 0; i < switchers.length; i++) {
      switchers[i].setAttribute("aria-expanded", "false");
    }
    for (var j = 0; j < btns.length; j++) {
      btns[j].setAttribute("aria-expanded", "false");
    }
    for (var k = 0; k < dropdowns.length; k++) {
      dropdowns[k].classList.remove("lang-switcher__dropdown--open");
    }
  }

  /* ─────────────────────────────────────────────
     Close when clicking outside the switcher
  ───────────────────────────────────────────── */
  document.addEventListener("click", function (e) {
    var switcher = document.querySelector("#lang-switcher");
    if (switcher && !switcher.contains(e.target)) {
      _closeAll();
    }
  });

  /* ─────────────────────────────────────────────
     Mount the switcher into a given container
  ───────────────────────────────────────────── */
  function mount(container) {
    if (!container) return;
    container.innerHTML = _buildHTML();
    _wireEvents(container);
  }

  /* ─────────────────────────────────────────────
     Auto-mount on elements with data-lang-mount
  ───────────────────────────────────────────── */
  function _autoMount() {
    var mounts = document.querySelectorAll("[data-lang-mount]");
    for (var i = 0; i < mounts.length; i++) {
      mount(mounts[i]);
    }
  }

  /* ─────────────────────────────────────────────
     Inject styles if not already present
  ───────────────────────────────────────────── */
  function _injectStyles() {
    if (document.getElementById("lang-switcher-styles")) return;
    var style = document.createElement("style");
    style.id = "lang-switcher-styles";
    style.textContent = [
      "/* ── Language Switcher Component ─────────────────── */",
      ".lang-switcher {",
      "  position: relative;",
      "  display: inline-flex;",
      "  align-items: center;",
      "}",
      ".lang-switcher__btn {",
      "  display: inline-flex;",
      "  align-items: center;",
      "  gap: 6px;",
      "  padding: 7px 12px;",
      "  border-radius: 9999px;",
      "  border: 1.5px solid rgba(0,69,50,0.2);",
      "  background: rgba(255,255,255,0.9);",
      "  color: #004532;",
      "  font-size: 13px;",
      "  font-weight: 600;",
      "  font-family: inherit;",
      "  cursor: pointer;",
      "  white-space: nowrap;",
      "  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;",
      "  outline: none;",
      "  line-height: 1;",
      "}",
      ".lang-switcher__btn:hover {",
      "  background: #e8f5ee;",
      "  border-color: rgba(0,69,50,0.4);",
      "}",
      ".lang-switcher__btn:focus-visible {",
      "  box-shadow: 0 0 0 3px rgba(0,69,50,0.3);",
      "}",
      "/* On dark backgrounds (landing page) */",
      ".lang-switcher--dark .lang-switcher__btn {",
      "  background: rgba(255,255,255,0.12);",
      "  border-color: rgba(255,255,255,0.3);",
      "  color: #fff;",
      "}",
      ".lang-switcher--dark .lang-switcher__btn:hover {",
      "  background: rgba(255,255,255,0.22);",
      "}",
      ".lang-switcher__icon {",
      "  width: 15px;",
      "  height: 15px;",
      "  flex-shrink: 0;",
      "}",
      ".lang-switcher__chevron {",
      "  width: 12px;",
      "  height: 12px;",
      "  flex-shrink: 0;",
      "  transition: transform 0.2s ease;",
      "}",
      "[aria-expanded='true'] .lang-switcher__chevron {",
      "  transform: rotate(180deg);",
      "}",
      ".lang-switcher__dropdown {",
      "  position: absolute;",
      "  top: calc(100% + 8px);",
      "  right: 0;",
      "  min-width: 160px;",
      "  background: #ffffff;",
      "  border: 1px solid rgba(0,69,50,0.12);",
      "  border-radius: 14px;",
      "  box-shadow: 0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);",
      "  padding: 6px;",
      "  z-index: 999;",
      "  opacity: 0;",
      "  pointer-events: none;",
      "  transform: translateY(-6px) scale(0.97);",
      "  transition: opacity 0.18s ease, transform 0.18s ease;",
      "  transform-origin: top right;",
      "}",
      ".lang-switcher__dropdown--open {",
      "  opacity: 1;",
      "  pointer-events: auto;",
      "  transform: translateY(0) scale(1);",
      "}",
      ".lang-switcher__dropdown-header {",
      "  font-size: 10px;",
      "  font-weight: 700;",
      "  text-transform: uppercase;",
      "  letter-spacing: 0.08em;",
      "  color: #6f7973;",
      "  padding: 6px 10px 4px;",
      "}",
      ".lang-option {",
      "  display: flex;",
      "  align-items: center;",
      "  justify-content: space-between;",
      "  gap: 8px;",
      "  width: 100%;",
      "  padding: 9px 10px;",
      "  border-radius: 9px;",
      "  border: none;",
      "  background: transparent;",
      "  color: #1b1c1a;",
      "  font-size: 14px;",
      "  font-family: inherit;",
      "  font-weight: 500;",
      "  cursor: pointer;",
      "  text-align: left;",
      "  transition: background 0.12s;",
      "  outline: none;",
      "}",
      ".lang-option:hover, .lang-option:focus-visible {",
      "  background: #f0f9f4;",
      "  color: #004532;",
      "}",
      ".lang-option--active {",
      "  background: #e8f5ee;",
      "  color: #004532;",
      "  font-weight: 700;",
      "}",
      ".lang-option__native {",
      "  font-size: 14px;",
      "  line-height: 1.3;",
      "}",
      ".lang-option__check {",
      "  font-size: 14px;",
      "  color: #004532;",
      "  flex-shrink: 0;",
      "}",
      "/* Responsive: ensure dropdown doesn't overflow viewport */",
      "@media (max-width: 480px) {",
      "  .lang-switcher__dropdown {",
      "    right: auto;",
      "    left: 0;",
      "    transform-origin: top left;",
      "    min-width: 140px;",
      "  }",
      "}"
    ].join("\n");
    document.head.appendChild(style);
  }

  /* ─────────────────────────────────────────────
     Expose public API
  ───────────────────────────────────────────── */
  global.CropMandiLangSwitcher = {
    mount: mount
  };

  /* Run on DOM ready */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      _injectStyles();
      _autoMount();
    });
  } else {
    _injectStyles();
    _autoMount();
  }

})(window);
