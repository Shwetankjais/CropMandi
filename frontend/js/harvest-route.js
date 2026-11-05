(function () {
  "use strict";

  var cfg = window.CropMandiConfig || {};

  var apiUrl = cfg.apiUrl || function (path) {
    return "http://127.0.0.1:8001" + path;
  };

  var coords = null;

  var form = document.getElementById("route-form");
  var commodity = document.getElementById("commodity");
  var series = document.getElementById("series");
  var originInput = document.getElementById("origin");
  var quantityInput = document.getElementById("quantity");
  var vehicleSelect = document.getElementById("vehicle_id");
  var modeAutoRadio = document.getElementById("mode_auto");
  var modeManualRadio = document.getElementById("mode_manual");
  var ownershipHiredRadio = document.getElementById("ownership_hired");
  var ownershipOwnedRadio = document.getElementById("ownership_owned");

  var statusEl = document.getElementById("form-status");
  var resultsEl = document.getElementById("results");
  var planBtn = document.getElementById("plan-btn");
  var mapStatusEl = document.getElementById("map-status");

  // Vehicle preview elements
  var previewVehicleName = document.getElementById("preview-vehicle-name");
  var previewTrustPill = document.getElementById("preview-trust-pill");
  var previewPayload = document.getElementById("preview-payload");
  var previewTrips = document.getElementById("preview-trips");
  var previewRate = document.getElementById("preview-rate");
  var previewVerified = document.getElementById("preview-verified");
  var previewWarning = document.getElementById("preview-warning");

  var map = null;
  var mapLayers = null;
  var marketMarkers = {};
  var routeLayers = {};

  var routeColors = [
    "#2563eb", // Rank #1: Vibrant Blue
    "#7c3aed", // Rank #2: Purple
    "#d97706", // Rank #3: Warm Amber / Orange
    "#059669", // Rank #4: Emerald Green
    "#dc2626"  // Rank #5: Crimson Red
  ];

  var defaultVehicles = [
    {
      id: "goods_auto",
      category: "Goods Auto / Cargo Three-Wheeler",
      model: "Mahindra Alfa Cargo / Piaggio Ape Truck",
      fuel_type: "petrol",
      usable_payload_kg: 450,
      max_payload_kg: 500,
      base_hire_rate_per_km: 12.0,
      data_source: "Mahindra Alfa Cargo specs; industry operator estimate",
      last_verified: "2024-10-01",
      confidence: 0.85
    },
    {
      id: "tata_ace",
      category: "Mini Truck / Tata Ace",
      model: "Tata Ace Gold (1-tonne)",
      fuel_type: "diesel",
      usable_payload_kg: 900,
      max_payload_kg: 1000,
      base_hire_rate_per_km: 18.0,
      data_source: "Tata Motors Ace Gold GVW spec sheet; IRTMF 2024",
      last_verified: "2024-10-01",
      confidence: 0.90
    },
    {
      id: "pickup_lcv",
      category: "Pickup / Light Commercial Vehicle",
      model: "Mahindra Bolero Pik-Up / Tata Yodha 2.0",
      fuel_type: "diesel",
      usable_payload_kg: 1350,
      max_payload_kg: 1500,
      base_hire_rate_per_km: 22.0,
      data_source: "Mahindra Bolero Pikup payload spec; IRTMF operator surveys 2024",
      last_verified: "2024-10-01",
      confidence: 0.85
    },
    {
      id: "medium_truck",
      category: "Medium Commercial Truck",
      model: "Tata LPT 1109 / Ashok Leyland Dost+ Heavy",
      fuel_type: "diesel",
      usable_payload_kg: 6700,
      max_payload_kg: 7500,
      base_hire_rate_per_km: 32.0,
      data_source: "Tata LPT 1109 GVW 10.5T payload spec; IRTMF 2024",
      last_verified: "2024-10-01",
      confidence: 0.85
    },
    {
      id: "truck_6w",
      category: "6-Wheeler Truck",
      model: "Tata LPT 1615 / Ashok Leyland Ecomet 1515",
      fuel_type: "diesel",
      usable_payload_kg: 9000,
      max_payload_kg: 10000,
      base_hire_rate_per_km: 45.0,
      data_source: "Tata LPT 1615 payload spec; IRTMF 2024",
      last_verified: "2024-10-01",
      confidence: 0.85
    },
    {
      id: "truck_10w",
      category: "10-Wheeler / Heavy Truck",
      model: "Tata LPT 2518 / Ashok Leyland 2518",
      fuel_type: "diesel",
      usable_payload_kg: 14400,
      max_payload_kg: 16000,
      base_hire_rate_per_km: 65.0,
      data_source: "Tata LPT 2518 GVW 25T payload spec; IRTMF 2024",
      last_verified: "2024-10-01",
      confidence: 0.85
    },
    {
      id: "multi_axle",
      category: "Multi-Axle Truck",
      model: "Tata Signa 4225.S / Ashok Leyland 3718",
      fuel_type: "diesel",
      usable_payload_kg: 22500,
      max_payload_kg: 25000,
      base_hire_rate_per_km: 95.0,
      data_source: "Tata Signa 4225.S GVW 42T payload spec; IRTMF 2024",
      last_verified: "2024-10-01",
      confidence: 0.80
    }
  ];

  var vehiclesCatalogue = defaultVehicles;

  /* =========================================
     UTILITY FUNCTIONS
  ========================================= */

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/[&<>"']/g, function (ch) {
        return {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;"
        }[ch];
      });
  }

  function rupees(value) {
    return value == null
      ? "Not available"
      : "₹" + Number(value).toLocaleString("en-IN", {
          maximumFractionDigits: 0
        });
  }

  function setStatus(message, isError) {
    statusEl.textContent = message || "";
    statusEl.className = "status" + (isError ? " error" : "");
  }

  function setMapStatus(message, isError) {
    if (!mapStatusEl) return;
    mapStatusEl.textContent = message || "";
    mapStatusEl.className = "map-status" + (isError ? " error" : "");
  }

  function getSelectedVehicle() {
    var id = vehicleSelect ? vehicleSelect.value : "tata_ace";
    for (var i = 0; i < vehiclesCatalogue.length; i++) {
      if (vehiclesCatalogue[i].id === id) {
        return vehiclesCatalogue[i];
      }
    }
    return vehiclesCatalogue[1] || vehiclesCatalogue[0];
  }

  function findAutoVehicle(qty) {
    for (var i = 0; i < vehiclesCatalogue.length; i++) {
      var v = vehiclesCatalogue[i];
      if (v.usable_payload_kg >= qty) {
        return v;
      }
    }
    return vehiclesCatalogue[vehiclesCatalogue.length - 1];
  }

  function updateVehiclePreview() {
    var qty = Number(quantityInput.value) || 500;
    var isAuto = modeAutoRadio && modeAutoRadio.checked;
    var v = isAuto ? findAutoVehicle(qty) : getSelectedVehicle();

    if (!v) return;

    if (previewVehicleName) {
      previewVehicleName.textContent = (isAuto ? "Recommended: " : "") + v.model;
    }

    if (previewPayload) {
      previewPayload.textContent = v.usable_payload_kg.toLocaleString("en-IN") + " kg";
    }

    var trips = Math.max(1, Math.ceil(qty / v.usable_payload_kg));
    if (previewTrips) {
      previewTrips.textContent = trips + (trips === 1 ? " trip" : " trips");
    }

    if (previewRate) {
      previewRate.textContent = "₹" + (v.base_hire_rate_per_km || 18).toFixed(2) + " / km";
    }

    if (previewVerified) {
      previewVerified.textContent = v.last_verified || "2024-10-01";
    }

    if (previewWarning) {
      if (qty > v.usable_payload_kg) {
        previewWarning.style.display = "block";
        if (trips > 20) {
          previewWarning.textContent = "⚠️ Load of " + qty.toLocaleString("en-IN") + " kg requires " + trips + " trips with this vehicle. Consider a higher capacity truck.";
        } else {
          previewWarning.textContent = "ℹ️ Harvest (" + qty.toLocaleString("en-IN") + " kg) exceeds single load (" + v.usable_payload_kg.toLocaleString("en-IN") + " kg). " + trips + " trips will be calculated.";
        }
      } else {
        previewWarning.style.display = "none";
      }
    }

    if (isAuto && vehicleSelect) {
      vehicleSelect.value = v.id;
    }
  }

  function loadVehiclesFromApi() {
    fetch(apiUrl("/api/harvest/vehicles"))
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data && data.vehicles && data.vehicles.length) {
          vehiclesCatalogue = data.vehicles;
          if (vehicleSelect) {
            var currentVal = vehicleSelect.value;
            vehicleSelect.innerHTML = "";
            vehiclesCatalogue.forEach(function (v) {
              var opt = document.createElement("option");
              opt.value = v.id;
              opt.textContent = v.category + " (" + v.model + ", " + v.usable_payload_kg.toLocaleString("en-IN") + " kg)";
              vehicleSelect.appendChild(opt);
            });
            if (currentVal) vehicleSelect.value = currentVal;
          }
          updateVehiclePreview();
        }
      })
      .catch(function () {
        // Fall back to embedded defaultVehicles gracefully
        updateVehiclePreview();
      });
  }

  /* =========================================
     LOAD CROP VARIETIES
  ========================================= */

  function loadSeries() {
    series.innerHTML = '<option value="">Loading…</option>';

    fetch(
      apiUrl(
        "/api/markets/rankings?commodity=" +
        encodeURIComponent(commodity.value) +
        "&limit=5"
      )
    )
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            throw new Error(
              body.message ||
              body.detail ||
              "Could not load crop varieties"
            );
          }
          return body;
        });
      })
      .then(function (data) {
        var options = data.series_options || [];
        series.innerHTML = "";

        if (!options.length) {
          series.innerHTML = '<option value="">Standard Variety / All Grades</option>';
          return;
        }

        options.forEach(function (option, index) {
          var item = document.createElement("option");
          item.value = option.value;
          item.textContent = option.label || option.value;
          if (index === 0) {
            item.selected = true;
          }
          series.appendChild(item);
        });
      })
      .catch(function (error) {
        series.innerHTML = '<option value="">Standard Variety / All Grades</option>';
        setStatus(error.message, true);
      });
  }

  /* =========================================
     INITIALIZE LEAFLET MAP
  ========================================= */

  function initMap() {
    if (map) return true;

    var mapElement = document.getElementById("harvest-map");

    if (!window.L || !mapElement) {
      setMapStatus(
        "Leaflet did not load. Check your internet connection, Leaflet CDN requests and the map container.",
        true
      );
      return false;
    }

    try {
      map = window.L.map("harvest-map", {
        scrollWheelZoom: false
      }).setView([13.05, 76.0], 7);

      var tiles = window.L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>'
        }
      );

      tiles.addTo(map);

      tiles.on("tileerror", function (event) {
        console.error("OpenStreetMap tile error:", event);
        setMapStatus(
          "The map loaded but some map tiles could not be retrieved. Check your network.",
          true
        );
      });

      tiles.on("load", function () {
        setMapStatus(
          "OpenStreetMap ready. Compare markets & routes to display recommended destinations."
        );
      });

      mapLayers = window.L.layerGroup().addTo(map);

      window.setTimeout(function () {
        if (map) {
          map.invalidateSize();
        }
      }, 250);

      return true;
    } catch (error) {
      console.error("Map initialization error:", error);
      setMapStatus(
        "The interactive map could not be initialized: " + error.message,
        true
      );
      return false;
    }
  }

  /* =========================================
     CUSTOM MAP MARKERS
  ========================================= */

  function makePin(kind, label) {
    return window.L.divIcon({
      className: "cm-map-div-icon",
      html: '<span class="cm-map-pin ' + kind + '">' + escapeHtml(label) + "</span>",
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -15]
    });
  }

  function validLatLng(value) {
    return (
      Array.isArray(value) &&
      value.length >= 2 &&
      Number.isFinite(Number(value[0])) &&
      Number.isFinite(Number(value[1])) &&
      Math.abs(Number(value[0])) <= 90 &&
      Math.abs(Number(value[1])) <= 180
    );
  }

  /* =========================================
     RENDER FARM AND MARKET ROUTES
  ========================================= */

  function renderMap(data) {
    if (!initMap()) return;

    mapLayers.clearLayers();
    marketMarkers = {};
    routeLayers = {};

    var bounds = [];
    var origin = data.origin_coordinates;
    var markerCount = 0;
    var routeCount = 0;
    var markets = data.markets || [];
    var locationCounts = {};

    /* FARM MARKER */
    if (validLatLng(origin)) {
      var originPoint = [Number(origin[0]), Number(origin[1])];

      var farmMarker = window.L.marker(originPoint, {
        icon: makePin("farm", "F"),
        title: "Farm location: " + (data.origin || "Your farm"),
        zIndexOffset: 1000
      })
        .bindPopup(
          "<div style='min-width:160px;font-family:sans-serif;'>" +
          "<span style='display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:800;background:#075b43;color:#fff;'>FARM ORIGIN</span>" +
          "<h4 style='margin:6px 0 2px;font-size:13px;'>" + escapeHtml(data.origin || "Your farm") + "</h4>" +
          "<div style='font-size:11px;color:#555;'>Dispatch Point (" + Number(origin[0]).toFixed(4) + ", " + Number(origin[1]).toFixed(4) + ")</div>" +
          "</div>"
        )
        .addTo(mapLayers);

      bounds.push(originPoint);
      markerCount += 1;
    }

    /* MARKET MARKERS AND ROAD ROUTES */
    markets.forEach(function (market, index) {
      var destination = market.destination_coordinates;
      var rankNum = market.recommendation_order || (index + 1);
      var isTop = rankNum === 1;
      var color = routeColors[(rankNum - 1) % routeColors.length] || "#2563eb";

      /* MARKET MARKER (ALL RECOMMENDED MANDIS) */
      if (validLatLng(destination)) {
        var rawLat = Number(destination[0]);
        var rawLng = Number(destination[1]);

        // Disambiguate overlapping markers at the same town/coordinates
        var coordKey = rawLat.toFixed(3) + "," + rawLng.toFixed(3);
        var dupIndex = locationCounts[coordKey] || 0;
        locationCounts[coordKey] = dupIndex + 1;

        var markerLat = rawLat;
        var markerLng = rawLng;
        if (dupIndex > 0) {
          // Offset subsequent markers by ~320m in a circle so every marker is visible and clickable
          var angle = (dupIndex * 2 * Math.PI) / 5;
          var offsetDist = 0.0032;
          markerLat += offsetDist * Math.cos(angle);
          markerLng += offsetDist * Math.sin(angle);
        }

        var destinationPoint = [markerLat, markerLng];

        var vSummary = market.vehicle_summary || {};
        var trips = vSummary.trips || 1;
        var vehicleLabel = vSummary.vehicle_model || vSummary.vehicle_category || "Commercial Vehicle";

        var popupHtml =
          "<div style='min-width:190px;font-family:sans-serif;line-height:1.45;'>" +
          "<div style='display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:800;background:" +
          (isTop ? "#075b43;color:#fff;" : "#f0f5f1;color:#075b43;") + "'>" +
          (isTop ? "⭐ #1 TOP PROFIT" : "#" + rankNum + " RECOMMENDED MANDI") +
          "</div>" +
          "<h4 style='margin:6px 0 2px;font-size:13px;'>" + escapeHtml(market.market_name || market.town || "Market") + "</h4>" +
          "<div style='font-size:11px;color:#555;margin-bottom:6px;'>" + escapeHtml(market.town || "") + "</div>" +
          (market.price ? "<div style='font-size:11px;'><strong>Mandi Price:</strong> " + rupees(market.price) + (market.unit ? " / " + escapeHtml(market.unit) : "") + "</div>" : "") +
          (market.distance_km != null ? "<div style='font-size:11px;'><strong>Road Distance:</strong> " + escapeHtml(market.distance_km) + " km" + (market.duration_min != null ? " (" + Math.round(market.duration_min) + " min)" : "") + "</div>" : "<div style='font-size:11px;color:#b43b36;'>Road route unavailable</div>") +
          "<div style='font-size:11px;'><strong>Vehicle:</strong> " + escapeHtml(vehicleLabel) + " · " + trips + (trips === 1 ? " trip" : " trips") + "</div>" +
          (market.transport_estimate_inr != null ? "<div style='font-size:11px;'><strong>Transport Cost:</strong> " + rupees(market.transport_estimate_inr) + "</div>" : "") +
          (market.net_estimate_inr != null ? "<div style='font-size:13px;font-weight:800;color:#075b43;margin-top:6px;padding-top:4px;border-top:1px solid #ddd;'>Est. Net: " + rupees(market.net_estimate_inr) + "</div>" : "") +
          (market.route_url ? "<div style='margin-top:6px;'><a href='" + escapeHtml(market.route_url) + "' target='_blank' rel='noopener' style='font-size:11px;color:#075b43;font-weight:700;'>Driving directions ↗</a></div>" : "") +
          "</div>";

        var marker = window.L.marker(destinationPoint, {
          icon: makePin("market" + (isTop ? " top-pin" : ""), String(rankNum)),
          title: "#" + rankNum + " " + (market.market_name || market.town || "Market"),
          zIndexOffset: isTop ? 500 : (100 - rankNum)
        })
          .bindPopup(popupHtml)
          .addTo(mapLayers);

        marketMarkers[index] = marker;
        bounds.push(destinationPoint);
        markerCount += 1;
      }

      /* ROAD ROUTE GEOMETRY */
      var geometry = market.route_geometry;

      if (
        geometry &&
        geometry.type === "LineString" &&
        Array.isArray(geometry.coordinates) &&
        geometry.coordinates.length > 1
      ) {
        var line = window.L.geoJSON(geometry, {
          style: {
            color: color,
            weight: isTop ? 6 : 4,
            opacity: isTop ? 0.92 : 0.72,
            lineCap: "round",
            lineJoin: "round"
          }
        }).addTo(mapLayers);

        routeLayers[index] = line;

        if (line.getBounds && line.getBounds().isValid()) {
          var lineBounds = line.getBounds();
          bounds.push(lineBounds.getSouthWest(), lineBounds.getNorthEast());
        }

        routeCount += 1;
      }
    });

    /* AUTOMATIC MAP ZOOM & BOUNDS */
    if (bounds.length) {
      map.fitBounds(window.L.latLngBounds(bounds), {
        padding: [35, 35],
        maxZoom: 11
      });
    } else {
      map.setView([13.05, 76.0], 7);
    }

    window.setTimeout(function () {
      if (map) {
        map.invalidateSize();
      }
    }, 120);

    /* MAP STATUS */
    if (!markerCount) {
      setMapStatus(
        "No mapped coordinates were returned. Check the farm location and try again.",
        true
      );
    } else if (!routeCount) {
      setMapStatus(
        markerCount + " recommended mandi location(s) plotted. Road geometry was unavailable; use driving directions links.",
        false
      );
    } else {
      setMapStatus(
        "Showing " + routeCount + " road route(s) and " + markerCount + " recommended mandi marker(s). Marker numbers correspond to profit ranking."
      );
    }
  }

  function focusMarket(index) {
    if (!map || !marketMarkers[index]) return;
    var marker = marketMarkers[index];
    map.setView(marker.getLatLng(), 11, { animate: true });
    marker.openPopup();

    // Highlight route if available
    if (routeLayers[index]) {
      routeLayers[index].setStyle({ weight: 7, opacity: 1.0 });
      if (routeLayers[index].bringToFront) {
        routeLayers[index].bringToFront();
      }
    }
  }

  /* =========================================
     RENDER MARKET CARDS
  ========================================= */

  function render(data) {
    var markets = data.markets || [];

    document.getElementById("results-subtitle").textContent =
      data.commodity.toUpperCase() +
      " · " +
      (data.selected_series || "all available grades") +
      " · " +
      Number(data.quantity_kg).toLocaleString("en-IN") +
      " kg";

    renderMap(data);

    if (!markets.length) {
      resultsEl.innerHTML =
        '<div class="empty">No suitable market routes were returned. Try another crop or origin.</div>';
      return;
    }

    resultsEl.innerHTML = markets.map(function (market, index) {
      var isTop = index === 0;
      var profit = market.profit_breakdown;
      var vSummary = market.vehicle_summary || {};
      var trips = vSummary.trips || 1;
      var vehicleName = vSummary.vehicle_model || vSummary.vehicle_category || "Commercial Vehicle";

      var netPerKg = profit && profit.net_per_kg
        ? " (₹" + profit.net_per_kg.toFixed(2) + " / kg)"
        : "";

      var html = '<article class="market' + (isTop ? ' top-mandi' : '') + '">';

      // Top row
      html += '<div class="market-top">';
      html += '<div>';
      html += '<h3>' + escapeHtml(market.market_name || market.town || "Market") + '</h3>';
      html += '<small>' + escapeHtml(market.town || "Town location unavailable") + '</small>';
      html += '</div>';
      html += '<span class="rank ' + (isTop ? 'top-choice' : '') + '">#' +
              escapeHtml(market.recommendation_order || (index + 1)) +
              (isTop ? ' · TOP PROFIT' : '') + '</span>';
      html += '</div>';

      // Net realization headline
      if (market.net_estimate_inr != null) {
        html += '<div class="net-headline">';
        html += '<div>';
        html += '<span class="net-headline-title">Estimated Net Realization</span>';
        html += '<span class="net-per-kg">' + escapeHtml(netPerKg) + '</span>';
        html += '</div>';
        html += '<span class="net-headline-amount">' + rupees(market.net_estimate_inr) + '</span>';
        html += '</div>';
      }

      // "Why this mandi?" callout
      if (market.recommendation_basis) {
        html += '<div class="why-mandi">💡 <strong>Why this market:</strong> ' + escapeHtml(market.recommendation_basis) + '</div>';
      }

      // Key stats grid
      var valueStats = [
        ["Road distance", market.distance_km == null ? "Unavailable" : market.distance_km + " km"],
        ["Travel time", market.duration_min == null ? "Unavailable" : Math.round(market.duration_min) + " min"],
        ["Mandi price", rupees(market.price) + (market.unit ? " / " + escapeHtml(market.unit) : "")],
        ["Vehicle & trips", escapeHtml(vehicleName) + " · " + trips + (trips === 1 ? " trip" : " trips")],
        ["Transport expense", rupees(market.transport_estimate_inr)],
        ["Gross sale value", rupees(market.gross_estimate_inr)]
      ];

      html += '<div class="stats">';
      html += valueStats.map(function (stat) {
        return '<div class="stat"><span>' + stat[0] + '</span><strong>' + stat[1] + '</strong></div>';
      }).join("");
      html += '</div>';

      // Full calculation breakdown if available
      if (profit) {
        var breakdownId = "breakdown-" + index;
        html += '<div style="margin: 8px 0;">';
        html += '<button type="button" class="breakdown-toggle" onclick="var el=document.getElementById(\'' + breakdownId + '\'); el.style.display = el.style.display===\'none\'?\'table\':\'none\';">📊 View full deduction breakdown ▼</button>';
        html += '<table id="' + breakdownId + '" class="breakdown-table" style="display:none;">';
        html += '<thead><tr><th>Component</th><th>Amount (₹)</th><th>Rate / Basis</th></tr></thead>';
        html += '<tbody>';
        html += '<tr><td>Gross Crop Value</td><td>' + rupees(profit.gross_revenue) + '</td><td>' + escapeHtml(market.unit || "Mandi price") + '</td></tr>';
        html += '<tr><td>APMC Mandi Fee</td><td>- ' + rupees(profit.market_fee) + '</td><td>2% commission</td></tr>';
        html += '<tr><td>Handling & Loading</td><td>- ' + rupees(profit.handling_cost) + '</td><td>₹50 / quintal</td></tr>';
        html += '<tr><td>Transport Cost</td><td>- ' + rupees(profit.total_transport_cost) + '</td><td>' + trips + ' trip(s) × ₹' + (vSummary.base_rate_per_km || 0).toFixed(2) + '/km</td></tr>';
        html += '<tr><td><strong>Net Realization</strong></td><td><strong>' + rupees(profit.net_realization) + '</strong></td><td><strong>₹' + profit.net_per_kg.toFixed(2) + ' / kg</strong></td></tr>';
        html += '</tbody></table>';
        html += '</div>';
      }

      // Foot
      html += '<div class="market-foot">';
      html += '<small>Price: ' + escapeHtml(market.price_date || "Recent") + ' · <span class="trust-pill ' + (market.price_freshness === 'recent' ? 'live' : 'estimate') + '">' + escapeHtml(market.price_freshness || "CONFIGURED") + '</span></small>';
      html += '<div class="actions">';
      html += '<button type="button" class="map-focus" data-map-focus="' + index + '">Locate on map</button>';
      html += '<a href="' + escapeHtml(market.route_url) + '" target="_blank" rel="noopener">Driving directions ↗</a>';
      html += '</div>';
      html += '</div>';

      html += '</article>';
      return html;
    }).join("");

    // Attach click handlers
    Array.prototype.forEach.call(
      resultsEl.querySelectorAll("[data-map-focus]"),
      function (button) {
        button.addEventListener("click", function () {
          focusMarket(Number(button.getAttribute("data-map-focus")));
        });
      }
    );

    // Limitations
    var notes = (data.limitations || []).join(" ");
    if (data.unit_note) {
      notes = data.unit_note + " " + notes;
    }
    var box = document.getElementById("limitations");
    if (box) {
      box.hidden = !notes;
      box.textContent = notes;
    }
  }

  /* =========================================
     EVENT LISTENERS
  ========================================= */

  if (commodity) {
    commodity.addEventListener("change", loadSeries);
  }

  if (originInput) {
    originInput.addEventListener("input", function () {
      coords = null;
    });
  }

  if (quantityInput) {
    quantityInput.addEventListener("input", updateVehiclePreview);
  }

  if (vehicleSelect) {
    vehicleSelect.addEventListener("change", function () {
      if (modeManualRadio) modeManualRadio.checked = true;
      updateVehiclePreview();
    });
  }

  if (modeAutoRadio) {
    modeAutoRadio.addEventListener("change", updateVehiclePreview);
  }

  if (modeManualRadio) {
    modeManualRadio.addEventListener("change", updateVehiclePreview);
  }

  if (ownershipHiredRadio) {
    ownershipHiredRadio.addEventListener("change", updateVehiclePreview);
  }

  if (ownershipOwnedRadio) {
    ownershipOwnedRadio.addEventListener("change", updateVehiclePreview);
  }

  /* GPS BUTTON */
  var gpsBtn = document.getElementById("gps-btn");
  if (gpsBtn) {
    gpsBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        setStatus("This browser does not support GPS location.", true);
        return;
      }

      setStatus("Requesting location permission…");

      navigator.geolocation.getCurrentPosition(
        function (position) {
          coords = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          };
          originInput.value = "My current farm location";
          setStatus("GPS location captured for this calculation.");
        },
        function () {
          setStatus(
            "Location permission was denied or unavailable. Enter your town and district instead.",
            true
          );
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000
        }
      );
    });
  }

  /* =========================================
     HARVEST ROUTE FORM SUBMISSION
  ========================================= */

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var isAuto = modeAutoRadio ? modeAutoRadio.checked : true;
    var selectedOwnership = (ownershipOwnedRadio && ownershipOwnedRadio.checked) ? "owned" : "hired";

    var payload = {
      commodity: commodity.value,
      series: series.value || null,
      origin: originInput.value.trim(),
      quantity_kg: Number(quantityInput.value),
      vehicle_mode: isAuto ? "auto" : "manual",
      vehicle_id: isAuto ? null : vehicleSelect.value,
      ownership: selectedOwnership,
      limit: 5
    };

    if (coords) {
      payload.latitude = coords.latitude;
      payload.longitude = coords.longitude;
    }

    if (!payload.origin || !(payload.quantity_kg > 0)) {
      setStatus("Please enter a valid farm location and harvest quantity.", true);
      return;
    }

    planBtn.disabled = true;
    planBtn.textContent = "Calculating routes & profit…";

    setStatus("Comparing market net realizations across candidate mandis. Geocoding town centres…");
    setMapStatus("Looking up farm and market coordinates and evaluating route profitability…");
    resultsEl.innerHTML = '<div class="empty">Calculating vehicle-specific net returns for your harvest…</div>';

    fetch(apiUrl("/api/harvest/routes"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            throw new Error(body.detail || body.message || "Route calculation failed");
          }
          return body;
        });
      })
      .then(function (data) {
        render(data);
        setStatus("Market net realization comparison generated. Confirm prices with the mandi before dispatch.");
      })
      .catch(function (error) {
        console.error("Harvest Route request failed:", error);
        resultsEl.innerHTML = '<div class="empty">' + escapeHtml(error.message) + '</div>';
        setStatus(error.message, true);
        setMapStatus("Route request failed: " + error.message, true);
      })
      .finally(function () {
        planBtn.disabled = false;
        planBtn.textContent = "Compare markets & routes";
      });
  });

  /* =========================================
     PAGE INITIALIZATION
  ========================================= */

  initMap();
  loadSeries();
  loadVehiclesFromApi();

})();
