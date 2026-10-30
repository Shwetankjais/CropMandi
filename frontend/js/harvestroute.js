(function () {
  "use strict";
  var API = window.CropMandiAPI;
  var state = { lat: null, lon: null, map: null, markers: [], pendingMandi: null, mapSdkLoaded: false, cropOptions: null };
  var $ = function (id) { return document.getElementById(id); };
  var api = API ? API.baseUrl : "http://127.0.0.1:8001";
  var cropNames = { tomato: "Tomato", maize: "Maize", paddy: "Paddy", potato: "Potato" };

  function fmtINR(value) {
    var n = Number(value);
    return Number.isFinite(n) ? "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—";
  }
  function setText(id, text) { var node = $(id); if (node) node.textContent = text == null ? "" : String(text); }
  function setHtml(id, html) { var node = $(id); if (node) node.innerHTML = html; }
  function showGlobal(message) { var node = $("global-notice"); if (!node) return; node.textContent = message || ""; node.classList.toggle("hidden", !message); }
  function option(select, value, label) { var el = document.createElement("option"); el.value = value; el.textContent = label; select.appendChild(el); }
  function getJson(path, query) {
    var url = new URL(api + path);
    Object.keys(query || {}).forEach(function (k) { if (query[k] !== undefined && query[k] !== null && query[k] !== "") url.searchParams.set(k, query[k]); });
    return fetch(url.toString(), { headers: { Accept: "application/json" } }).then(readResponse);
  }
  function postJson(path, body, extraHeaders) {
    var headers = { "Content-Type": "application/json", Accept: "application/json" };
    Object.keys(extraHeaders || {}).forEach(function (key) { headers[key] = extraHeaders[key]; });
    return fetch(api + path, { method: "POST", headers: headers, body: JSON.stringify(body || {}) }).then(readResponse);
  }
  function readResponse(response) {
    return response.json().catch(function () { return {}; }).then(function (body) {
      if (!response.ok) throw new Error(body.detail || body.message || body.error || ("Request failed (" + response.status + ")"));
      return body;
    });
  }
  function selectedMarket() {
    try { return JSON.parse($("market-select").value || "{}"); } catch (_) { return {}; }
  }
  function selectedFarmerLocation() {
    var lat = Number($("latitude").value), lon = Number($("longitude").value);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) throw new Error("Set a valid farmer latitude and longitude first.");
    state.lat = lat; state.lon = lon;
    return { latitude: lat, longitude: lon };
  }
  function tableMessage(id, message, colspan) {
    setHtml(id, "<table><tbody><tr><td colspan='" + (colspan || 5) + "' class='text-center muted'>" + message + "</td></tr></tbody></table>");
  }

  function loadModels() {
    getJson("/api/crops/models").then(function (payload) {
      var cards = $("model-status-cards"); cards.innerHTML = "";
      (payload.models || []).forEach(function (model) {
        var el = document.createElement("div"); el.className = "metric";
        var label = document.createElement("span"); label.className = "eyebrow"; label.textContent = model.name;
        var strong = document.createElement("strong"); strong.textContent = Number(model.observation_count || 0).toLocaleString("en-IN");
        var sub = document.createElement("span"); sub.className = "text-xs muted";
        sub.textContent = model.model_status === "READY" ? (model.feature_count + " features · " + model.market_count + " markets") : model.model_status;
        el.appendChild(label); el.appendChild(strong); el.appendChild(sub); cards.appendChild(el);
      });
      if (payload.feature_assumptions) {
        var assumptions = payload.feature_assumptions;
        showGlobal("Models loaded. Feature/target definitions are partially inferred; " + assumptions.target_semantics + " Current accuracy is not established by these runtime checks.");
      }
    }).catch(function (err) { showGlobal("Could not load model status: " + err.message); });
  }

  function updateSeriesControls() {
    var market = selectedMarket();
    var series = market.series_options || [];
    var variety = $("variety-select"), grade = $("grade-select");
    var previousVariety = variety.value, previousGrade = grade.value;
    var varieties = Array.from(new Set(series.map(function (x) { return x.variety; })));
    variety.innerHTML = "";
    varieties.forEach(function (v) { var count = Math.max.apply(null, series.filter(function (x) { return x.variety === v; }).map(function (x) { return x.observation_count; })); option(variety, v, v + (Number.isFinite(count) ? " · max " + count + " records" : "")); });
    if (varieties.indexOf(previousVariety) !== -1) variety.value = previousVariety;
    var allowedGrades = series.filter(function (x) { return x.variety === variety.value; }).map(function (x) { return x.grade; });
    grade.innerHTML = "";
    allowedGrades.forEach(function (g) { var count = (series.find(function (x) { return x.variety === variety.value && x.grade === g; }) || {}).observation_count; option(grade, g, g + (count ? " · " + count + " records" : "")); });
    if (allowedGrades.indexOf(previousGrade) !== -1) grade.value = previousGrade;
    if (!varieties.length) option(variety, "", "No series");
    if (!allowedGrades.length) option(grade, "", "No grade");
    var selectedSeries = series.find(function (x) { return x.variety === variety.value && x.grade === grade.value; });
    setText("series-caption", market.market_name ? market.market_name + " · " + (market.district || "") + " · " + (selectedSeries ? selectedSeries.observation_count + " observations" + (selectedSeries.prediction_ready ? " · prediction ready" : " · needs 8+ observations") : series.length + " combinations") : "No market selected");
  }

  function loadCropOptions() {
    var crop = $("crop-select").value;
    getJson("/api/crops/options", { crop: crop }).then(function (payload) {
      state.cropOptions = payload;
      var market = $("market-select");
      market.innerHTML = "";
      (payload.markets || []).forEach(function (m) { option(market, JSON.stringify(m), m.market_name + (m.district ? " · " + m.district : "")); });
      if (!market.options.length) option(market, "", "No market data");
      updateSeriesControls();
      loadHistory();
    }).catch(function (err) {
      var tbody = $("history-rows"); if (tbody) { tbody.innerHTML = ""; var tr = document.createElement("tr"); var td = document.createElement("td"); td.colSpan = 5; td.textContent = "Could not load crop options: " + err.message; tr.appendChild(td); tbody.appendChild(tr); }
    });
  }

  function loadHistory() {
    var market = selectedMarket();
    if (!market.market_name || !$("variety-select").value || !$("grade-select").value) return;
    getJson("/api/crops/history", {
      crop: $("crop-select").value, market_name: market.market_name, district: market.district,
      variety: $("variety-select").value, grade: $("grade-select").value, limit: 30,
    }).then(function (payload) {
      var tbody = $("history-rows"); tbody.innerHTML = "";
      if (!payload.records.length) {
        var emptyTr = document.createElement("tr"); var emptyTd = document.createElement("td");
        emptyTd.colSpan = 5; emptyTd.className = "muted text-center"; emptyTd.textContent = "No matching observations.";
        emptyTr.appendChild(emptyTd); tbody.appendChild(emptyTr); return;
      }
      payload.records.slice().reverse().forEach(function (row) {
        var tr = document.createElement("tr");
        [row.date, Number(row.arrivals).toLocaleString("en-IN") + " " + row.unit, fmtINR(row.min_price), fmtINR(row.max_price), fmtINR(row.modal_price)].forEach(function (v) { var td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
        tbody.appendChild(tr);
      });
      setText("series-caption", market.market_name + " · " + (market.district || "") + " · " + $("variety-select").value + " · " + $("grade-select").value + " · " + payload.count + " records");
    }).catch(function (err) { tableMessage("history-rows", "History unavailable: " + err.message, 5); });
  }

  function runPrediction() {
    var market = selectedMarket();
    if (!market.market_name) { setText("prediction-result", "Select a market first."); return; }
    var button = $("run-prediction"); button.disabled = true; button.textContent = "Running model…";
    postJson("/api/crops/predict", {
      crop: $("crop-select").value, market_name: market.market_name, district: market.district,
      variety: $("variety-select").value, grade: $("grade-select").value,
    }).then(function (p) {
      var output = p.prediction_kind === "price_level"
        ? "<strong class='text-2xl text-emerald-900'>" + fmtINR(p.predicted_modal_price) + "</strong><div class='text-xs muted'>Model output · " + p.unit + " · " + p.prediction_date + "</div>"
        : "<strong class='text-2xl text-emerald-900'>" + fmtINR(p.predicted_delta) + "</strong><div class='text-xs muted'>Raw model delta · " + p.unit + " · " + p.prediction_date + "</div><div class='mt-2'>Indicative base + delta: <strong>" + fmtINR(p.indicative_modal_price_if_delta_is_next_session_change) + "</strong></div>";
      setHtml("prediction-result", output + "<p class='text-xs muted mt-3'>Based on " + p.history_observations_used + " market observations; latest record " + p.latest_observation_date + ". Feature construction: " + p.feature_engineering_status + ". Actual model accuracy is not yet validated.</p><p class='text-xs text-amber-800 mt-2'>" + (p.display_label || "Experimental model output") + "</p>");
    }).catch(function (err) { setText("prediction-result", "Prediction unavailable: " + err.message); })
      .finally(function () { button.disabled = false; button.textContent = "Run selected crop model"; });
  }

  function loadMapplsMap(center) {
    getJson("/api/location/map-config").then(function (config) {
      var status = $("mappls-status");
      if (!config.map_sdk_configured) {
        status.textContent = config.rest_api_configured ? "REST ready · map key missing" : "Mappls keys not configured";
        return;
      }
      if (state.mapSdkLoaded) { renderMap(center); return; }
      var script = document.createElement("script");
      script.src = "https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=" + encodeURIComponent(config.map_sdk_key);
      script.onload = function () {
        state.mapSdkLoaded = true; status.textContent = "Mappls map ready";
        var mapNode = $("map"); if (mapNode) mapNode.innerHTML = "";
        renderMap(center);
      };
      script.onerror = function () { status.textContent = "Map SDK failed to load"; };
      document.head.appendChild(script);
    }).catch(function (err) { setText("mappls-status", "Map config unavailable"); });
  }

  function renderMap(center, mandis) {
    if (!window.mappls || !window.mappls.Map) return;
    try {
      if (!state.map) state.map = new window.mappls.Map("map", { center: { lat: center.latitude, lng: center.longitude }, zoom: 8 });
      else if (state.map.setCenter) state.map.setCenter([center.longitude, center.latitude]);
      state.markers.forEach(function (marker) { try { marker.remove(); } catch (_) {} }); state.markers = [];
      if (window.mappls.Marker) {
        state.markers.push(new window.mappls.Marker({ map: state.map, position: { lat: center.latitude, lng: center.longitude }, popupHtml: "Farmer location" }));
        (mandis || []).forEach(function (m) {
          state.markers.push(new window.mappls.Marker({ map: state.map, position: { lat: m.latitude, lng: m.longitude }, popupHtml: m.name + " · " + (m.district || "") }));
        });
      }
    } catch (err) { setText("mappls-status", "Map view could not initialize"); }
  }

  function setLocation(lat, lon, accuracy, label) {
    state.lat = Number(lat); state.lon = Number(lon);
    $("latitude").value = state.lat; $("longitude").value = state.lon;
    setText("location-caption", label || ("Location set · " + (accuracy ? "GPS accuracy ±" + Math.round(accuracy) + " m" : "coordinates supplied manually")));
    postJson("/api/location/capture", { latitude: state.lat, longitude: state.lon, accuracy_m: accuracy || null, purpose: "current_phone_location", language: "en" })
      .then(function (payload) {
        var result = payload.reverse_geocode && payload.reverse_geocode.result;
        if (result && result.formatted_address) setText("location-caption", result.formatted_address + (accuracy ? " · GPS ±" + Math.round(accuracy) + " m" : ""));
      }).catch(function () {});
    loadMapplsMap({ latitude: state.lat, longitude: state.lon });
    $("find-nearby").disabled = false;
  }

  function useGPS() {
    if (!navigator.geolocation) { showGlobal("This browser does not support geolocation. Enter a village address or coordinates manually."); return; }
    $("use-gps").disabled = true; $("use-gps").textContent = "Requesting location…";
    navigator.geolocation.getCurrentPosition(function (position) {
      setLocation(position.coords.latitude, position.coords.longitude, position.coords.accuracy, "GPS location received. Not stored.");
      $("use-gps").disabled = false; $("use-gps").textContent = "Use my current location";
    }, function (err) {
      showGlobal("Could not access GPS: " + err.message + ". You can enter a village/address or coordinates instead.");
      $("use-gps").disabled = false; $("use-gps").textContent = "Use my current location";
    }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 });
  }

  function geocodeAddress() {
    var address = $("manual-address").value.trim();
    if (!address) { showGlobal("Enter a village, taluk, district or farm address."); return; }
    $("geocode-address").disabled = true;
    postJson("/api/location/geocode", { address: address + ", Karnataka, India" }).then(function (p) {
      setLocation(p.latitude, p.longitude, null, p.formatted_address || address + " · Mappls location suggestion");
      showGlobal("Address geocoded by Mappls. Check that the pin matches the farm or collection point.");
    }).catch(function (err) { showGlobal("Address geocoding failed: " + err.message); }).finally(function () { $("geocode-address").disabled = false; });
  }

  function loadNearby() {
    var origin;
    try { origin = selectedFarmerLocation(); } catch (err) { showGlobal(err.message); return; }
    $("find-nearby").disabled = true; $("find-nearby").textContent = "Searching…";
    getJson("/api/markets/nearby", { latitude: origin.latitude, longitude: origin.longitude, radius_km: $("radius-select").value, limit: 10, profile: $("route-profile").value })
      .then(function (p) {
        if (!p.mandis.length) { tableMessage("nearby-results", p.message || "No geocoded markets found.", 4); return; }
        var html = "<table><thead><tr><th>Mandi</th><th>District</th><th>Distance</th><th>ETA</th><th>Coordinate status</th></tr></thead><tbody>";
        p.mandis.forEach(function (m) { html += "<tr><td class='font-semibold'>" + esc(m.name) + "</td><td>" + esc(m.district) + "</td><td>" + m.distance_km + " km</td><td>" + (m.duration_minutes == null ? "—" : m.duration_minutes + " min") + "</td><td>" + esc(m.coordinate_status || m.distance_type) + "</td></tr>"; });
        html += "</tbody></table>";
        setHtml("nearby-results", html);
        if (p.notice) setText("location-caption", p.notice);
        renderMap(origin, p.mandis);
      }).catch(function (err) { tableMessage("nearby-results", "Mandi search failed: " + err.message, 5); })
      .finally(function () { $("find-nearby").disabled = false; $("find-nearby").textContent = "Find nearby mandis"; });
  }

  function esc(value) { return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) { return ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]; }); }

  function loadMandiDirectory() {
    getJson("/api/mandis", { limit: 250 }).then(function (p) {
      var select = $("mandi-select"); select.innerHTML = "";
      p.mandis.forEach(function (m) { option(select, String(m.id), m.name + " · " + (m.district || "District unknown") + (m.is_verified ? " · verified" : " · unverified")); });
      if (!p.mandis.length) option(select, "", "No market records");
    }).catch(function (err) { setText("geocode-result", "Could not load market directory: " + err.message); });
  }

  function geocodeMandi() {
    var id = Number($("mandi-select").value); if (!id) return;
    $("geocode-mandi").disabled = true; $("geocode-mandi").textContent = "Geocoding…";
    postJson("/api/mandis/geocode", { mandi_id: id }).then(function (p) {
      state.pendingMandi = p;
      setText("geocode-result", p.name + " · " + p.formatted_address + " · " + p.latitude + ", " + p.longitude + " · confidence: " + (p.confidence || "not supplied") + ". " + p.message);
      $("confirm-mandi").disabled = false;
      if (state.lat != null) renderMap({ latitude: state.lat, longitude: state.lon }, [{ name: p.name, district: p.district, latitude: p.latitude, longitude: p.longitude }]);
      loadMandiDirectory();
    }).catch(function (err) { setText("geocode-result", "Mappls geocoding failed: " + err.message); }).finally(function () { $("geocode-mandi").disabled = false; $("geocode-mandi").textContent = "Geocode selected market with Mappls"; });
  }

  function confirmMandi() {
    var m = state.pendingMandi; if (!m) return;
    var adminToken = $("admin-coordinate-token").value.trim();
    if (!adminToken) { setText("geocode-result", "Enter the server-configured mandi coordinate admin token before confirming."); return; }
    postJson("/api/mandis/" + m.mandi_id + "/confirm", { latitude: m.latitude, longitude: m.longitude }, { "X-Mandi-Admin-Token": adminToken }).then(function () {
      setText("geocode-result", m.name + " coordinates marked MANUALLY_CONFIRMED. Verify the market entrance in Mappls before using this in production.");
      $("confirm-mandi").disabled = true; state.pendingMandi = null; loadMandiDirectory();
    }).catch(function (err) { setText("geocode-result", "Could not confirm coordinates: " + err.message); });
  }

  function runOptimizer() {
    var origin; try { origin = selectedFarmerLocation(); } catch (err) { showGlobal(err.message); return; }
    var market = selectedMarket();
    var payload = {
      origin: origin, crop: $("crop-select").value, variety: $("variety-select").value || null,
      grade: $("grade-select").value || null, quantity_quintal: Number($("quantity-qtl").value),
      profile: $("route-profile").value, rate_per_km: Number($("rate-km").value),
      fixed_transport_cost: Number($("fixed-cost").value), handling_cost: Number($("handling-cost").value),
      round_trip: $("round-trip").checked, market_fee_percent: Number($("market-fee").value),
      loss_percent: Number($("loss-pct").value), radius_km: Number($("radius-select").value),
    };
    if (!Number.isFinite(payload.quantity_quintal) || payload.quantity_quintal <= 0) { showGlobal("Enter a positive produce quantity in quintals."); return; }
    $("run-optimizer").disabled = true; $("run-optimizer").textContent = "Calculating…";
    postJson("/api/harvestroute/optimize", payload).then(function (p) {
      if (!p.results.length) { tableMessage("optimizer-results", p.message || "No results.", 7); setText("optimizer-notice", "No market candidates could be evaluated."); return; }
      var html = "<table><thead><tr><th>Rank / mandi</th><th>Price</th><th>Distance</th><th>Transport</th><th>Gross value</th><th>Net return</th><th>Date</th></tr></thead><tbody>";
      p.results.forEach(function (r) { html += "<tr><td><strong>#" + r.rank + " " + esc(r.name) + "</strong><div class='muted text-xs'>" + esc(r.district) + "</div></td><td>" + fmtINR(r.price) + " / qtl</td><td>" + r.distance_km + " km" + (r.duration_minutes == null ? "" : "<div class='muted text-xs'>" + r.duration_minutes + " min</div>") + "</td><td>" + fmtINR(r.transport_cost) + "</td><td>" + fmtINR(r.gross_sale_value) + "</td><td class='font-bold text-emerald-900'>" + fmtINR(r.estimated_net_return) + "</td><td>" + esc(r.price_date) + "</td></tr>"; });
      html += "</tbody></table>"; setHtml("optimizer-results", html);
      setText("optimizer-notice", p.provider + (p.is_road_distance ? " · Mappls road distances and ETA" : " · Straight-line distance only — not a road route") + (p.notice ? " · " + p.notice : "") + " · " + p.important_note);
    }).catch(function (err) { tableMessage("optimizer-results", "Optimizer failed: " + err.message, 7); })
      .finally(function () { $("run-optimizer").disabled = false; $("run-optimizer").textContent = "Calculate net-return ranking"; });
  }

  function init() {
    if (!API) { showGlobal("CropMandi API helper missing. Open this page from the supplied project and start the backend on port 8001."); return; }
    $("crop-select").addEventListener("change", loadCropOptions);
    $("market-select").addEventListener("change", function () { updateSeriesControls(); loadHistory(); });
    $("variety-select").addEventListener("change", function () { updateSeriesControls(); loadHistory(); });
    $("grade-select").addEventListener("change", loadHistory);
    $("load-history").addEventListener("click", loadHistory);
    $("run-prediction").addEventListener("click", runPrediction);
    $("refresh-models").addEventListener("click", loadModels);
    $("use-gps").addEventListener("click", useGPS);
    $("geocode-address").addEventListener("click", geocodeAddress);
    $("find-nearby").addEventListener("click", loadNearby);
    $("geocode-mandi").addEventListener("click", geocodeMandi);
    $("confirm-mandi").addEventListener("click", confirmMandi);
    $("run-optimizer").addEventListener("click", runOptimizer);
    loadModels(); loadCropOptions(); loadMandiDirectory();
    getJson("/api/location/map-config").then(function (c) { setText("mappls-status", c.rest_api_configured ? (c.map_sdk_configured ? "Mappls connected" : "REST enabled · map SDK key missing") : "Mappls API key required"); }).catch(function () { setText("mappls-status", "Mappls unavailable"); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
