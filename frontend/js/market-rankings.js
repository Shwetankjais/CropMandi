/**
 * Cross-market price rankings for every supported CropMandi commodity.
 * Rankings are supplied by the API; this file only renders the returned data.
 */
(function () {
  "use strict";

  var CROP_LABELS = {
    coffee: "Coffee",
    pepper: "Black Pepper",
    rice: "Rice",
    tomato: "Tomato",
    maize: "Maize",
    paddy: "Paddy",
    potato: "Potato",
  };
  var requestSequence = 0;
  var cropSelect;
  var seriesSelect;
  var rowsBody;
  var statusEl;
  var errorEl;
  var noteEl;
  var sourceEl;
  var methodEl;

  function $(id) {
    return document.getElementById(id);
  }

  function setVisible(el, visible) {
    if (el) {
      el.classList.toggle("hidden", !visible);
    }
  }

  function setLoading(loading) {
    setVisible(statusEl, loading);
    setVisible(errorEl, false);
    if (statusEl && loading) {
      statusEl.textContent = "Loading market rankings…";
    }
    if (cropSelect) cropSelect.disabled = loading;
    if (seriesSelect) seriesSelect.disabled = loading || !seriesSelect.options.length;
    if (loading && rowsBody) {
      rowsBody.innerHTML = "";
      var tr = document.createElement("tr");
      var td = document.createElement("td");
      td.colSpan = 5;
      td.className = "px-3 py-5 text-center text-on-surface-variant";
      td.textContent = "Loading latest available market observations…";
      tr.appendChild(td);
      rowsBody.appendChild(tr);
    }
  }

  function addEmptyRow(message) {
    if (!rowsBody) return;
    rowsBody.innerHTML = "";
    var tr = document.createElement("tr");
    var td = document.createElement("td");
    td.colSpan = 5;
    td.className = "px-3 py-5 text-center text-on-surface-variant";
    td.textContent = message;
    tr.appendChild(td);
    rowsBody.appendChild(tr);
  }

  function formatPrice(value, unit) {
    var number = Number(value);
    if (!Number.isFinite(number)) return "—";
    var formatted = "₹" + number.toLocaleString("en-IN", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
    var suffix = "";
    if (unit === "Rs./50 Kg") suffix = " / 50 kg";
    else if (unit === "INR_PER_QUINTAL") suffix = " / quintal";
    else if (unit === "INR_PER_KG") suffix = " / kg";
    else if (unit) suffix = " / " + String(unit).replace(/_/g, " ").toLowerCase();
    return formatted + suffix;
  }

  function statusLabel(payload) {
    if (payload.data_status === "UNVERIFIED_LOCAL_DATA") {
      return "Unverified local workbook data";
    }
    if (payload.data_status === "AGMARKNET_INGESTED") {
      return "AGMARKNET observations";
    }
    if (payload.data_status === "NO_DATA_AVAILABLE") {
      return "No observations available";
    }
    return String(payload.data_status || "Data status unavailable").replace(/_/g, " ");
  }

  function fillSeriesOptions(options, selectedValue) {
    if (!seriesSelect) return;
    seriesSelect.innerHTML = "";
    (options || []).forEach(function (option) {
      var element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      seriesSelect.appendChild(element);
    });
    if (selectedValue && Array.prototype.some.call(seriesSelect.options, function (option) {
      return option.value === selectedValue;
    })) {
      seriesSelect.value = selectedValue;
    }
    seriesSelect.disabled = !seriesSelect.options.length;
    if (!seriesSelect.options.length) {
      var emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "No varieties available";
      seriesSelect.appendChild(emptyOption);
      seriesSelect.disabled = true;
    }
  }

  function renderRows(payload) {
    if (!payload.rankings || !payload.rankings.length) {
      var cropName = CROP_LABELS[payload.commodity] || payload.commodity;
      addEmptyRow(
        payload.data_status === "NO_DATA_AVAILABLE"
          ? "No price observations are currently stored for " + cropName + ". Rankings will appear after valid market data is ingested."
          : "No valid market observations are available for this variety or grade."
      );
      return;
    }

    rowsBody.innerHTML = "";
    payload.rankings.forEach(function (item) {
      var tr = document.createElement("tr");
      tr.className = "border-b border-outline-variant/10";

      var rankCell = document.createElement("td");
      rankCell.className = "px-3 py-3 font-bold text-primary whitespace-nowrap";
      rankCell.textContent = "#" + item.rank;

      var marketCell = document.createElement("td");
      marketCell.className = "px-3 py-3 text-on-background font-semibold min-w-[190px]";
      marketCell.textContent = item.market_name || "Unknown market";

      var locationCell = document.createElement("td");
      locationCell.className = "px-3 py-3 text-on-surface-variant min-w-[130px]";
      locationCell.textContent = Array.isArray(item.locations) && item.locations.length
        ? item.locations.join(" · ")
        : "—";

      var priceCell = document.createElement("td");
      priceCell.className = "px-3 py-3 text-right text-primary font-bold whitespace-nowrap";
      priceCell.textContent = formatPrice(item.price, item.unit);

      var dateCell = document.createElement("td");
      dateCell.className = "px-3 py-3 text-right text-on-surface-variant whitespace-nowrap";
      dateCell.textContent = item.date || "—";
      if (item.freshness_status === "HISTORICAL") {
        var historicalLabel = document.createElement("span");
        historicalLabel.className = "block text-xs text-error mt-0.5";
        historicalLabel.textContent = "Historical · " + item.age_days + " days old";
        dateCell.appendChild(historicalLabel);
      }

      tr.appendChild(rankCell);
      tr.appendChild(marketCell);
      tr.appendChild(locationCell);
      tr.appendChild(priceCell);
      tr.appendChild(dateCell);
      rowsBody.appendChild(tr);
    });
  }

  function renderPayload(payload) {
    fillSeriesOptions(payload.series_options, payload.selected_series);
    renderRows(payload);

    if (methodEl) {
      methodEl.textContent = (payload.ranking_method ||
        "Latest available observation per market, ranked from highest to lowest.") +
        " These are stored observations, not live quotes. Rows older than 30 days are marked Historical; verify today's rate before selling.";
    }
    if (noteEl) {
      if (payload.count) {
        noteEl.textContent = "Showing the top " + payload.count + " of " + payload.total_markets +
          " available markets for " + (payload.series_options.find(function (item) {
            return item.value === payload.selected_series;
          }) || {}).label + ". Latest observation date in this set: " + (payload.as_of || "—") + ".";
      } else {
        noteEl.textContent = "The ranking list is based only on observations currently available in the project data store.";
      }
    }
    if (sourceEl) {
      var pieces = [statusLabel(payload)];
      if (payload.source) pieces.push("Source: " + payload.source);
      if (payload.provenance && payload.provenance !== payload.source) pieces.push(payload.provenance);
      if (payload.unit_note) pieces.push(payload.unit_note);
      sourceEl.textContent = pieces.join(" · ");
    }
  }

  function loadRankings() {
    if (!window.CropMandiAPI || typeof CropMandiAPI.getMarketRankings !== "function") {
      setVisible(errorEl, true);
      errorEl.textContent = "Market ranking API is not available. Start the CropMandi backend and reload this page.";
      addEmptyRow("Ranking service unavailable.");
      return;
    }

    var sequence = ++requestSequence;
    var crop = cropSelect.value || "coffee";
    var series = seriesSelect && seriesSelect.value ? seriesSelect.value : "";
    setLoading(true);

    var request;
    if (["tomato", "maize", "paddy", "potato"].indexOf(crop) !== -1) {
      var vegetableQuery = { crop: crop, limit: 5 };
      if (series) {
        try {
          var selected = JSON.parse(series);
          vegetableQuery.variety = selected[0];
          vegetableQuery.grade = selected[1];
        } catch (e) { /* initial request: API chooses the first available series */ }
      }
      request = CropMandiAPI.getJson("/api/crops/rankings", vegetableQuery);
    } else {
      request = CropMandiAPI.getMarketRankings(crop, series, 5);
    }

    request
      .then(function (payload) {
        if (sequence !== requestSequence) return;
        setLoading(false);
        renderPayload(payload);
      })
      .catch(function (error) {
        if (sequence !== requestSequence) return;
        setLoading(false);
        setVisible(errorEl, true);
        errorEl.textContent = error && error.message
          ? error.message
          : "Unable to load market rankings. Please try again.";
        addEmptyRow("Market rankings could not be loaded.");
        if (noteEl) noteEl.textContent = "Check the backend connection and try again.";
      })
      .finally(function () {
        if (sequence === requestSequence) {
          if (cropSelect) cropSelect.disabled = false;
          if (seriesSelect && seriesSelect.options.length) {
            seriesSelect.disabled = false;
            if (seriesSelect.options.length === 1 && !seriesSelect.options[0].value) {
              seriesSelect.disabled = true;
            }
          }
        }
      });
  }

  function init() {
    cropSelect = $("dash-market-ranking-crop");
    seriesSelect = $("dash-market-ranking-series");
    rowsBody = $("dash-market-ranking-rows");
    statusEl = $("dash-market-ranking-status");
    errorEl = $("dash-market-ranking-error");
    noteEl = $("dash-market-ranking-note");
    sourceEl = $("dash-market-ranking-source");
    methodEl = $("dash-market-ranking-method");
    if (!cropSelect || !seriesSelect || !rowsBody) return;

    var savedCrop = localStorage.getItem("cropmandi_market_ranking_crop");
    if (savedCrop && CROP_LABELS[savedCrop]) {
      cropSelect.value = savedCrop;
    }

    cropSelect.addEventListener("change", function () {
      localStorage.setItem("cropmandi_market_ranking_crop", cropSelect.value);
      seriesSelect.innerHTML = "";
      var loading = document.createElement("option");
      loading.value = "";
      loading.textContent = "Loading varieties…";
      seriesSelect.appendChild(loading);
      seriesSelect.disabled = true;
      loadRankings();
    });

    seriesSelect.addEventListener("change", loadRankings);
    loadRankings();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
