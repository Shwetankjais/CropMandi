// Mandi Price AI Dashboard — JavaScript
// Connects to /api/mandi-price/* endpoints (ExtraTreesRegressor pipeline)
// ZERO impact on existing dashboard pages, scripts, or API routes.

(function (global) {
  "use strict";

  const API_BASE = (global.CropMandiAPI && global.CropMandiAPI.baseUrl)
    ? global.CropMandiAPI.baseUrl + "/api/mandi-price"
    : "http://127.0.0.1:8001/api/mandi-price";

  // ── DOM refs ────────────────────────────────────────────────────────────
  let cropSelect     = null;
  let marketSelect   = null;
  let targetDate     = null;
  let predictBtn     = null;
  let loadMarketsBtn = null;
  let resultCard     = null;
  let summaryCard    = null;
  let healthStatus   = null;

  // ── Helpers ─────────────────────────────────────────────────────────────
  function setStatus(el, html, cls) {
    if (!el) return;
    el.innerHTML = html;
    el.className = "mpa-status " + (cls || "");
  }

  function escapeHTML(s) {
    return String(s || "").replace(/[&<>"']/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    );
  }

  function localDateISO() {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
  }

  function tomorrowDateISO() {
    const t = new Date();
    t.setDate(t.getDate() + 1);
    const p = n => String(n).padStart(2, "0");
    return `${t.getFullYear()}-${p(t.getMonth()+1)}-${p(t.getDate())}`;
  }

  // ── Health check ────────────────────────────────────────────────────────
  async function checkHealth() {
    if (!healthStatus) return;
    try {
      const r = await fetch(`${API_BASE}/health`);
      const d = await r.json();
      const ok = d.model_ready && d.datasets_ready;
      setStatus(
        healthStatus,
        ok
          ? `<span class="mpa-ok">✅ Model ready — ${escapeHTML(d.supported_crops.join(", "))}</span>`
          : `<span class="mpa-warn">⚠️ Model or datasets not fully ready. model_ready=${d.model_ready}, datasets_ready=${d.datasets_ready}</span>`,
        ok ? "ok" : "warn"
      );
    } catch (e) {
      setStatus(healthStatus, `<span class="mpa-err">❌ API unreachable — ${escapeHTML(String(e))}</span>`, "err");
    }
  }

  // ── Load markets for selected crop ─────────────────────────────────────
  async function loadMarkets() {
    const crop = cropSelect && cropSelect.value;
    if (!crop) return;
    if (marketSelect) {
      marketSelect.innerHTML = '<option value="">Loading markets…</option>';
      marketSelect.disabled = true;
    }
    try {
      const r = await fetch(`${API_BASE}/markets?crop=${encodeURIComponent(crop)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (marketSelect) {
        if (d.markets && d.markets.length > 0) {
          marketSelect.innerHTML = d.markets.map(m =>
            `<option value="${escapeHTML(m)}">${escapeHTML(m)}</option>`
          ).join("");
        } else {
          marketSelect.innerHTML = '<option value="">No markets found</option>';
        }
        marketSelect.disabled = false;
      }
    } catch (e) {
      if (marketSelect) {
        marketSelect.innerHTML = '<option value="">Failed to load markets</option>';
        marketSelect.disabled = false;
      }
    }
  }

  // ── Quick crop tab switcher ─────────────────────────────────────────────
  global.setCrop = function (btn, crop) {
    document.querySelectorAll(".mpa-crop-tab").forEach(b => b.classList.remove("active"));
    if (btn) {
      btn.classList.add("active");
    } else {
      const match = document.querySelector(`.mpa-crop-tab[data-crop="${crop}"]`);
      if (match) match.classList.add("active");
    }
    if (cropSelect) {
      cropSelect.value = crop;
      loadMarkets();
    }
  };

  function syncTabsWithSelect() {
    if (!cropSelect) return;
    const crop = cropSelect.value;
    document.querySelectorAll(".mpa-crop-tab").forEach(tab => {
      if (tab.getAttribute("data-crop") === crop) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });
  }

  // ── Predict price ───────────────────────────────────────────────────────
  async function predict() {
    const crop   = cropSelect   && cropSelect.value;
    const market = marketSelect && marketSelect.value;
    const tDate  = targetDate   && targetDate.value;

    if (!crop || !market) {
      setStatus(resultCard, "Please select a crop and market first.", "warn");
      return;
    }

    if (predictBtn) predictBtn.disabled = true;
    setStatus(resultCard, "⏳ Computing forecast with ExtraTreesRegressor pipeline…", "");

    try {
      const r = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ crop, market, target_date: tDate || null }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);

      resultCard.innerHTML = `
        <div class="mpa-result-inner">
          <div class="flex items-center justify-between mb-2">
            <span class="mpa-crop-badge">${escapeHTML(d.crop.toUpperCase())}</span>
            <span class="text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-300">ML Forecast</span>
          </div>
          <div class="mpa-result-main">
            <span class="mpa-label">Predicted Modal Price</span>
            <span class="mpa-price">₹${Number(d.predicted_modal_price).toLocaleString("en-IN", {maximumFractionDigits: 2})}</span>
            <span class="mpa-unit">${escapeHTML(d.unit)}</span>
          </div>
          <dl class="mpa-meta">
            <dt>Market</dt>     <dd>${escapeHTML(d.market)}</dd>
            <dt>Date</dt>       <dd>${escapeHTML(d.target_date)}</dd>
            <dt>Model</dt>      <dd>${escapeHTML(d.model)}</dd>
            <dt>Data status</dt><dd>${escapeHTML(d.data_status)}</dd>
          </dl>
          <p class="mpa-disclaimer">${escapeHTML(d.important_note)}</p>
        </div>`;
    } catch (e) {
      setStatus(resultCard, `❌ ${escapeHTML(String(e.message || e))}`, "err");
    } finally {
      if (predictBtn) predictBtn.disabled = false;
    }
  }

  // ── Summary cards ───────────────────────────────────────────────────────
  async function loadSummary() {
    if (!summaryCard) return;
    summaryCard.innerHTML = "<p class='mpa-status'>Loading crop data summary…</p>";
    try {
      const r = await fetch(`${API_BASE}/crops/summary`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      summaryCard.innerHTML = `
        <div class="mpa-summary-grid">
          ${d.crops.map(c => `
            <div class="mpa-summary-item">
              <strong>${escapeHTML(c.crop.charAt(0).toUpperCase() + c.crop.slice(1))}</strong>
              <span>${c.market_count} markets</span>
              <span>${c.row_count.toLocaleString()} rows</span>
              <span class="mpa-date-range">${escapeHTML(c.date_range_from || "—")} → ${escapeHTML(c.date_range_to || "—")}</span>
            </div>
          `).join("")}
        </div>
        <p class="mpa-model-info">Model: <strong>${escapeHTML(d.model_type)}</strong> (${escapeHTML(d.model_artifact)}) — ready: ${d.model_ready ? "✅ Yes" : "❌ No"}</p>`;
    } catch (e) {
      summaryCard.innerHTML = `<p class="mpa-err">Could not load summary: ${escapeHTML(String(e))}</p>`;
    }
  }

  // ── Init function ────────────────────────────────────────────────────────
  function init() {
    cropSelect    = document.getElementById("mpa-crop");
    marketSelect  = document.getElementById("mpa-market");
    targetDate    = document.getElementById("mpa-date");
    predictBtn    = document.getElementById("mpa-predict-btn");
    loadMarketsBtn= document.getElementById("mpa-load-markets");
    resultCard    = document.getElementById("mpa-result");
    summaryCard   = document.getElementById("mpa-summary");
    healthStatus  = document.getElementById("mpa-health");

    if (loadMarketsBtn) loadMarketsBtn.addEventListener("click", loadMarkets);
    if (cropSelect) {
      cropSelect.addEventListener("change", function () {
        syncTabsWithSelect();
        loadMarkets();
      });
    }
    if (predictBtn) predictBtn.addEventListener("click", predict);

    if (targetDate && !targetDate.value) {
      targetDate.value = tomorrowDateISO();
    }

    try {
      const urlParams = new URLSearchParams(window.location.search);
      let targetCrop = (urlParams.get("commodity") || urlParams.get("crop") || "").toLowerCase().trim();
      if (targetCrop === "rice") targetCrop = "paddy";
      if (targetCrop === "corn") targetCrop = "maize";

      if (["paddy", "tomato", "potato", "maize"].includes(targetCrop)) {
        if (cropSelect) {
          cropSelect.value = targetCrop;
        }
      }
    } catch (_) {}

    checkHealth();
    loadSummary();
    if (cropSelect && cropSelect.value) {
      syncTabsWithSelect();
      loadMarkets();
    }

    try {
      const hash = window.location.hash;
      const urlParams = new URLSearchParams(window.location.search);
      const isTargeted = hash === "#mandi-price-ai" || urlParams.has("commodity") || urlParams.has("crop");
      if (isTargeted) {
        const targetSection = document.getElementById("mandi-price-ai");
        if (targetSection) {
          setTimeout(function () {
            targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 350);
        }
      }
    } catch (_) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})(window);
