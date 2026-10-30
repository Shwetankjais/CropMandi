/**
 * Next-session baseline estimate for the selected commodity series.
 * Uses GET /api/predictions/next. Does not invent prices or confidence.
 */
(function () {
  "use strict";

  var LOADING_MESSAGE = "Loading next-session estimate...";
  var ERROR_MESSAGE = "Unable to load the next-session estimate. Please try again.";
  var INSUFFICIENT_MESSAGE = "Prediction unavailable due to insufficient historical data.";
  var MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  var cropSelect;
  var seriesSelect;
  var locationSelect;
  var refreshButton;
  var statusEl;
  var errorEl;
  var bodyEl;
  var seriesEl;
  var locationEl;
  var latestPriceEl;
  var nextPriceEl;
  var latestDateEl;
  var targetEl;
  var unitEl;
  var methodEl;
  var modelStatusEl;
  var noteEl;
  var warningEl;
  var requestSeq = 0;

  function $(id) {
    return document.getElementById(id);
  }

  function commodity() {
    return cropSelect && cropSelect.value ? cropSelect.value : "coffee";
  }

  function selectedSeries() {
    return seriesSelect ? seriesSelect.value : "";
  }

  function formatPrice(value) {
    if (!Number.isFinite(value)) {
      return "—";
    }
    return "₹" + Number(value).toLocaleString("en-IN");
  }

  function formatDate(iso) {
    if (!iso) {
      return "Not yet known";
    }
    var parts = String(iso).split("-");
    if (parts.length !== 3) {
      return iso;
    }
    var monthIndex = Number(parts[1]) - 1;
    if (monthIndex < 0 || monthIndex > 11) {
      return iso;
    }
    return Number(parts[2]) + " " + MONTHS[monthIndex] + " " + parts[0];
  }

  function unitLabel(unit) {
    if (!unit) {
      return "—";
    }
    if (unit === "INR_PER_50KG") {
      return "Rs./50 Kg";
    }
    if (unit === "INR_PER_KG") {
      return "Rs./Kg";
    }
    return unit;
  }

  function setPredictionUnavailable(message) {
    window.CropMandiLastEstimate = { unavailable: true };
    var recCrop = $("dash-rec-crop");
    var recVariety = $("dash-rec-variety");
    if (recCrop) {
      recCrop.textContent = commodity() === "pepper" ? "Black Pepper" : "Coffee";
    }
    if (recVariety) {
      recVariety.textContent = selectedSeries() || "—";
    }
    if (nextPriceEl) {
      nextPriceEl.textContent = "—";
    }
  }

  function setLoading(isLoading) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = isLoading ? LOADING_MESSAGE : "";
    statusEl.classList.toggle("hidden", !isLoading);
    if (errorEl) {
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }
    if (bodyEl) {
      bodyEl.classList.toggle("opacity-60", isLoading);
    }
  }

  function showError(message) {
    setLoading(false);
    if (errorEl) {
      errorEl.textContent = message || INSUFFICIENT_MESSAGE;
      errorEl.classList.remove("hidden");
    }
    if (latestPriceEl) {
      latestPriceEl.textContent = "—";
    }
    if (nextPriceEl) {
      nextPriceEl.textContent = "—";
    }
    if (latestDateEl) {
      latestDateEl.textContent = "—";
    }
    if (targetEl) {
      targetEl.textContent = "—";
    }
    if (unitEl) {
      unitEl.textContent = "—";
    }
    if (methodEl) {
      methodEl.textContent = "";
    }
    if (modelStatusEl) {
      modelStatusEl.textContent = "";
    }
    if (noteEl) {
      noteEl.textContent = "";
    }
    if (warningEl) {
      warningEl.textContent = "";
    }
    setPredictionUnavailable(message || ERROR_MESSAGE);
  }

  function updateContext() {
    if (seriesEl) {
      seriesEl.textContent = selectedSeries() || "—";
    }
    if (!locationEl) {
      return;
    }
    var location = locationSelect && locationSelect.value;
    locationEl.textContent = location || "—";
  }

  function render(payload) {
    setLoading(false);
    window.CropMandiLastEstimate = payload;
    if (errorEl) {
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }
    var observedPrice = payload.latest_observed_price !== undefined ? payload.latest_observed_price : payload.price;
    var predPrice = payload.predicted_price !== undefined ? payload.predicted_price : payload.next_session_estimate;

    if (latestPriceEl) {
      latestPriceEl.textContent = formatPrice(observedPrice);
    }
    if (nextPriceEl) {
      nextPriceEl.textContent = formatPrice(predPrice);
    }
    if (latestDateEl) {
      latestDateEl.textContent = formatDate(payload.latest_observation_date);
    }
    if (targetEl) {
      var targetDateVal = payload.prediction_date || payload.target_session || payload.next_session;
      targetEl.textContent = targetDateVal ? formatDate(targetDateVal) : "—";
    }
    if (unitEl) {
      unitEl.textContent = payload.unit_display || unitLabel(payload.unit);
    }
    if (methodEl) {
      methodEl.textContent = payload.model_name
        ? "Model: " + payload.model_name
        : payload.method
        ? "Method: " + String(payload.method).replace(/_/g, " ")
        : "";
    }
    if (modelStatusEl) {
      modelStatusEl.textContent = payload.model_status
        ? "Model status: " + String(payload.model_status).replace(/_/g, " ")
        : "";
    }
    if (noteEl) {
      noteEl.textContent = payload.prediction_type === "ML prediction"
        ? "Trained ExtraTreesRegressor pipeline on 73k+ records. 15 features evaluated."
        : payload.note || "Baseline estimate repeating latest observed rate.";
    }
    if (warningEl) {
      warningEl.textContent = "";
    }

    // Difference pill
    var diffPill = $("dash-est-diff-pill");
    if (diffPill) {
      if (payload.price_diff !== undefined && payload.pct_change !== undefined) {
        var diff = payload.price_diff;
        var pct = payload.pct_change;
        var sign = diff > 0 ? "+" : "";
        diffPill.textContent = sign + formatPrice(diff) + " (" + sign + pct.toFixed(2) + "%)";
        diffPill.className = "text-xs font-bold px-2.5 py-0.5 rounded-full " + (diff > 0 ? "bg-primary/10 text-primary" : diff < 0 ? "bg-error/10 text-error" : "bg-surface-variant/20 text-on-surface-variant");
        diffPill.classList.remove("hidden");
      } else {
        diffPill.classList.add("hidden");
      }
    }

    // Gross Revenue card
    var grossEl = $("dash-est-gross-value");
    if (grossEl && payload.estimated_gross_value !== undefined) {
      grossEl.textContent = "₹" + Number(payload.estimated_gross_value).toLocaleString("en-IN");
    }
    var grossSub = $("dash-est-gross-sub");
    if (grossSub && payload.quantity) {
      grossSub.textContent = payload.quantity + " Quintals @ " + formatPrice(predPrice) + " / " + (payload.unit_display || payload.unit || "quintal");
    }

    var recCrop = $("dash-rec-crop");
    var recVariety = $("dash-rec-variety");
    if (recCrop) {
      recCrop.textContent = payload.commodity || (commodity() === "pepper" ? "Black Pepper" : commodity().charAt(0).toUpperCase() + commodity().slice(1));
    }
    if (recVariety) {
      recVariety.textContent = payload.variety || payload.series || selectedSeries() || "—";
    }
    updateContext();
  }

  function loadEstimate() {
    var code = commodity();
    var series = selectedSeries();
    var location = locationSelect ? locationSelect.value : "";
    var targetDateInput = $("dash-date");
    var targetDate = (targetDateInput && targetDateInput.value) ? targetDateInput.value : null;
    var qtyInput = $("dash-quantity");
    var quantity = qtyInput ? parseFloat(qtyInput.value) || 50 : 50;

    var seq = ++requestSeq;
    updateContext();
    setLoading(true);

    if (window.CropMandiAPI && CropMandiAPI.predictPrice) {
      var payload = {
        commodity: code,
        variety: series || "DEFAULT",
        grade: "AVERAGE",
        market: location || "DEFAULT",
        prediction_date: targetDate,
        quantity: quantity,
        quantity_unit: "quintal",
        user_id: window.CropMandiAuth ? CropMandiAuth.firstName() : "default_farmer"
      };

      CropMandiAPI.predictPrice(payload)
        .then(function (result) {
          if (seq !== requestSeq) return;
          if (!result || !result.success) {
            showError(ERROR_MESSAGE);
            return;
          }
          render(result);
        })
        .catch(function () {
          if (seq !== requestSeq) return;
          // Fallback to legacy endpoint if available
          if (CropMandiAPI.getNextSessionEstimate && (code === "coffee" || code === "pepper")) {
            CropMandiAPI.getNextSessionEstimate(code, series)
              .then(function (legacy) {
                if (seq !== requestSeq) return;
                render(legacy);
              })
              .catch(function () {
                showError(INSUFFICIENT_MESSAGE);
              });
          } else {
            showError(INSUFFICIENT_MESSAGE);
          }
        });
    } else {
      showError(ERROR_MESSAGE);
    }
  }

  function init() {
    cropSelect = $("dash-crop");
    seriesSelect = $("dash-series");
    locationSelect = $("dash-location");
    refreshButton = $("dash-refresh");
    statusEl = $("dash-est-status");
    errorEl = $("dash-est-error");
    bodyEl = $("dash-est-body");
    seriesEl = $("dash-est-series");
    locationEl = $("dash-est-location");
    latestPriceEl = $("dash-est-latest-price");
    nextPriceEl = $("dash-est-next-price");
    latestDateEl = $("dash-est-latest-date");
    targetEl = $("dash-est-target");
    unitEl = $("dash-est-unit");
    methodEl = $("dash-est-method");
    modelStatusEl = $("dash-est-model-status");
    noteEl = $("dash-est-note");
    warningEl = $("dash-est-warning");
    if (!cropSelect || !seriesSelect || !bodyEl) {
      return;
    }
    cropSelect.addEventListener("change", function () {
      setTimeout(loadEstimate, 200);
    });
    seriesSelect.addEventListener("change", loadEstimate);
    if (locationSelect) {
      locationSelect.addEventListener("change", function () {
        updateContext();
        loadEstimate();
      });
      if (window.MutationObserver) {
        new MutationObserver(updateContext).observe(locationSelect, {
          childList: true,
          subtree: true,
          attributes: true,
        });
      }
    }
    var dateInput = $("dash-date");
    if (dateInput) {
      dateInput.addEventListener("change", loadEstimate);
    }
    var qtyInput = $("dash-quantity");
    if (qtyInput) {
      qtyInput.addEventListener("change", loadEstimate);
    }
    var qtyInc = $("dash-qty-inc");
    if (qtyInc) {
      qtyInc.addEventListener("click", function () {
        setTimeout(loadEstimate, 100);
      });
    }
    var qtyDec = $("dash-qty-dec");
    if (qtyDec) {
      qtyDec.addEventListener("click", function () {
        setTimeout(loadEstimate, 100);
      });
    }
    if (refreshButton) {
      refreshButton.addEventListener("click", loadEstimate);
    }
    setTimeout(loadEstimate, 300);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
