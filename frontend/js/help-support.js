/**
 * CropMandi AI — Global Farmer Help & Support Modal
 * Provides instant agricultural assistance, Kisan call center helpline,
 * HarvestRoute guide, Mandi Price AI guide, and Voice Assistant instructions.
 */
(function (global) {
  "use strict";

  var MODAL_ID = "cropmandi-global-help-modal";

  function createHelpModal() {
    if (document.getElementById(MODAL_ID)) return;

    var modal = document.createElement("div");
    modal.id = MODAL_ID;
    modal.className = "cm-help-modal-backdrop";
    modal.style.cssText = [
      "position: fixed",
      "inset: 0",
      "z-index: 9999",
      "background: rgba(0, 30, 20, 0.65)",
      "backdrop-filter: blur(4px)",
      "display: none",
      "align-items: center",
      "justify-content: center",
      "padding: 16px",
      "font-family: 'DM Sans', Roboto, sans-serif",
    ].join(";");

    modal.innerHTML = [
      '<div class="cm-help-card" style="background:#fff; border-radius:18px; max-width:620px; width:100%; max-height:90vh; overflow-y:auto; box-shadow:0 20px 50px rgba(0,40,25,0.3); border:1px solid #c2d9cc; animation: cmFadeIn 0.2s ease;">',
      '  <div style="background:#004532; color:#fff; padding:20px 24px; border-radius:17px 17px 0 0; display:flex; justify-content:space-between; align-items:center;">',
      '    <div style="display:flex; align-items:center; gap:10px;">',
      '      <span style="font-size:26px;">🌾</span>',
      '      <div>',
      '        <h3 style="margin:0; font-size:18px; font-weight:800; font-family:\'Roboto Slab\',serif;">CropMandi AI — Farmer Help & Guide</h3>',
      '        <p style="margin:2px 0 0; font-size:12px; color:#8bd6b7;">Market Intelligence, Routing & Platform Support</p>',
      '      </div>',
      '    </div>',
      '    <button id="cm-help-close-btn" style="background:rgba(255,255,255,0.15); border:none; color:#fff; width:34px; height:34px; border-radius:50%; font-size:18px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background 0.2s;">✕</button>',
      '  </div>',
      '  <div style="padding:22px 24px; color:#1b2d22; font-size:13px; line-height:1.6;">',
      '    <!-- Emergency Kisan Helpline Banner -->',
      '    <div style="background:#f0f7f3; border:1px solid #b2dbca; border-left:4px solid #004532; border-radius:10px; padding:12px 16px; margin-bottom:18px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">',
      '      <div>',
      '        <strong style="color:#004532; font-size:14px; display:block;">📞 Kisan Call Centre (Toll-Free)</strong>',
      '        <span style="color:#4a6557; font-size:12px;">Government of India 24x7 Agricultural Helpline</span>',
      '      </div>',
      '      <a href="tel:18001801551" style="background:#004532; color:#fff; text-decoration:none; padding:8px 14px; border-radius:20px; font-weight:800; font-size:13px;">1800-180-1551</a>',
      '    </div>',
      '    <!-- Guide Sections -->',
      '    <div style="display:flex; flex-direction:column; gap:14px;">',
      '      <div style="background:#fafdfb; border:1px solid #e2ede6; border-radius:12px; padding:14px 16px;">',
      '        <strong style="color:#004532; font-size:14px; display:flex; align-items:center; gap:8px;">🚚 HarvestRoute — Smart Mandi & Transport</strong>',
      '        <p style="margin:4px 0 0; color:#4a6557;">HarvestRoute ranks all mandis by <strong>Net Realization (Profit)</strong>, not just proximity. It factors harvest weight, vehicle payload, number of round trips, diesel rates, and mandi market cess.</p>',
      '      </div>',
      '      <div style="background:#fafdfb; border:1px solid #e2ede6; border-radius:12px; padding:14px 16px;">',
      '        <strong style="color:#004532; font-size:14px; display:flex; align-items:center; gap:8px;">📈 Mandi Price AI — 4-Crop Forecasting</strong>',
      '        <p style="margin:4px 0 0; color:#4a6557;">Get next-session modal price forecasts for <strong>Tomato, Potato, Paddy, and Maize</strong> powered by our trained ExtraTreesRegressor model on AGMARKNET historical records.</p>',
      '      </div>',
      '      <div style="background:#fafdfb; border:1px solid #e2ede6; border-radius:12px; padding:14px 16px;">',
      '        <strong style="color:#004532; font-size:14px; display:flex; align-items:center; gap:8px;">🌱 My Crops — 7-Commodity Portfolio</strong>',
      '        <p style="margin:4px 0 0; color:#4a6557;">Track inventory and portfolio values across Coffee, Black Pepper, Cardamom, Paddy, Tomato, Potato, and Maize with one-click price forecast and market analytics.</p>',
      '      </div>',
      '      <div style="background:#fafdfb; border:1px solid #e2ede6; border-radius:12px; padding:14px 16px;">',
      '        <strong style="color:#004532; font-size:14px; display:flex; align-items:center; gap:8px;">🎙️ Voice Assistant (Multilingual)</strong>',
      '        <p style="margin:4px 0 0; color:#4a6557;">Click the microphone button to ask prices and navigate hands-free in <strong>English, Hindi (हिंदी), or Kannada (ಕನ್ನಡ)</strong>.</p>',
      '      </div>',
      '    </div>',
      '  </div>',
      '  <div style="padding:14px 24px; background:#f5f8f6; border-top:1px solid #e2ede6; border-radius:0 0 17px 17px; display:flex; justify-content:space-between; align-items:center;">',
      '    <span style="font-size:11px; color:#74897e;">CropMandi AI V1 · Production Ready</span>',
      '    <button id="cm-help-done-btn" style="background:#004532; color:#fff; border:none; padding:8px 20px; border-radius:8px; font-weight:700; cursor:pointer;">Got it</button>',
      '  </div>',
      '</div>'
    ].join("\n");

    document.body.appendChild(modal);

    function closeModal() {
      modal.style.display = "none";
    }

    var closeBtn = document.getElementById("cm-help-close-btn");
    var doneBtn = document.getElementById("cm-help-done-btn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (doneBtn) doneBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });
  }

  function openHelpModal() {
    createHelpModal();
    var modal = document.getElementById(MODAL_ID);
    if (modal) {
      modal.style.display = "flex";
    }
  }

  function bindHelpTriggers() {
    createHelpModal();
    document.addEventListener("click", function (e) {
      var target = e.target.closest("a, button");
      if (!target) return;
      var href = target.getAttribute("href");
      var isHelp =
        href === "#help" ||
        target.id === "dash-help-btn" ||
        target.id === "btn-top-help" ||
        target.textContent.trim().toLowerCase() === "help";
      if (isHelp) {
        e.preventDefault();
        openHelpModal();
      }
    });
  }

  global.CropMandiHelp = {
    open: openHelpModal,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindHelpTriggers);
  } else {
    bindHelpTriggers();
  }
})(window);

