/**
 * Cold-storage lookup for the dashboard location selector.
 * Does not invent availability, crop compatibility, or facilities.
 */
(function () {
  "use strict";

  var ERROR_MESSAGE = "Unable to load cold-storage records. Please try again.";
  var cropSelect;
  var dashCropSelect;
  var locationSelect;
  var locationLabel;
  var headingEl;
  var quantityInput;
  var searchButton;
  var statusEl;
  var errorEl;
  var listEl;
  var countEl;
  var routingEl;
  var requestSeq = 0;
  var storageMap = null;
  var storageMarkers = [];

  function $(id) {
    return document.getElementById(id);
  }

  function selectedLocation() {
    if (locationSelect && locationSelect.value) {
      return locationSelect.value;
    }
    return "";
  }

  function setLoading(isLoading) {
    if (statusEl) {
      statusEl.textContent = isLoading ? "Searching nearby cold storages..." : "";
      statusEl.classList.toggle("hidden", !isLoading);
    }
    if (errorEl) {
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }
    if (searchButton) {
      searchButton.disabled = isLoading;
    }
  }

  function showError(message) {
    setLoading(false);
    if (errorEl) {
      errorEl.textContent = message || ERROR_MESSAGE;
      errorEl.classList.remove("hidden");
    }
    if (listEl) {
      listEl.innerHTML = "";
    }
    if (countEl) {
      countEl.textContent = "";
    }
    var mapElHide = document.getElementById("dash-storage-map");
    if (mapElHide) { mapElHide.classList.add("hidden"); }
  }

  function capacityText(row) {
    if (row.capacity_mt === null || row.capacity_mt === undefined || row.capacity_mt === "") {
      return "Not available";
    }
    return row.capacity_mt + " MT";
  }

  function render(payload) {
    setLoading(false);
    var locationName = (payload && payload.requested_location) || selectedLocation() || "selected location";
    if (headingEl) {
      headingEl.textContent = "Cold Storage Near " + locationName;
    }
    if (locationLabel) {
      locationLabel.textContent = locationName;
    }
    var rows = (payload && payload.facilities) || [];
    if (countEl) {
      if (payload && payload.match_type === "NO_DATA") {
        countEl.textContent = "NO VERIFIED COLD STORAGE FOUND WITHIN 75 KM";
      } else if (payload && payload.match_type === "UNKNOWN_LOCATION") {
        countEl.textContent = "This location is not in the cold-storage catalog.";
      } else {
        countEl.textContent = rows.length ? "Cold Storage Near " + locationName : "NO VERIFIED COLD STORAGE FOUND WITHIN 75 KM";
      }
    }
    if (routingEl) {
      var hasRoad = rows.some(function(r) { return r.road_distance_km !== null && r.road_distance_km !== undefined; });
      routingEl.textContent = rows.length
        ? (hasRoad ? "Distance and travel time calculated via road routing (OSRM)." : "Distance is a straight-line estimate (Haversine).")
        : "";
    }
    if (!listEl) {
      return;
    }
    listEl.innerHTML = "";
    if (!rows.length) {
      var empty = document.createElement("li");
      empty.className = "text-on-surface-variant";
      empty.textContent = (payload && payload.message) || "NO VERIFIED COLD STORAGE FOUND WITHIN 75 KM";
      listEl.appendChild(empty);
      var mapElHide = document.getElementById("dash-storage-map");
      if (mapElHide) { mapElHide.classList.add("hidden"); }
      return;
    }
    rows.forEach(function (row, idx) {
      var li = document.createElement("li");
      li.className = "border border-outline-variant/40 rounded-xl p-3 bg-white hover:border-primary/40 transition-colors";

      var headerRow = document.createElement("div");
      headerRow.className = "flex items-start justify-between gap-2";

      var title = document.createElement("p");
      title.className = "text-sm font-semibold text-on-background";
      title.textContent = row.name || "Unnamed storage";
      headerRow.appendChild(title);

      var badge = document.createElement("span");
      badge.className = "text-xs font-bold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant flex-shrink-0";
      badge.textContent = "#" + (idx + 1);
      headerRow.appendChild(badge);

      li.appendChild(headerRow);

      var placeBits = [];
      if (row.district) {
        placeBits.push(row.district);
      } else if (row.location) {
        placeBits.push(row.location);
      }
      if (row.road_distance_km !== null && row.road_distance_km !== undefined) {
        var roadStr = row.road_distance_km + " km (road)";
        if (row.eta_minutes !== null && row.eta_minutes !== undefined) {
          roadStr += " · " + row.eta_minutes + " min";
        }
        placeBits.push(roadStr);
      } else if (row.distance_km !== null && row.distance_km !== undefined) {
        placeBits.push(row.distance_km + " km (straight-line)");
      }
      var place = document.createElement("p");
      place.className = "text-xs text-on-surface-variant mt-0.5";
      place.textContent = placeBits.join(" · ");
      li.appendChild(place);

      var facts = document.createElement("p");
      facts.className = "text-xs text-on-background mt-2";
      facts.textContent = "Capacity: " + capacityText(row);
      li.appendChild(facts);

      var source = document.createElement("p");
      source.className = "text-xs text-on-surface-variant mt-1";
      var sourceBits = ["Source: " + (row.source_name || row.source_label || row.source || "Unknown")];
      if (row.source_status) {
        sourceBits.push(row.source_status);
      }
      if (row.last_verified_at) {
        sourceBits.push(row.last_verified_at);
      }
      source.textContent = sourceBits.join(" · ");
      li.appendChild(source);

      if (row.address || row.phone || row.commodities_label) {
        var extra = document.createElement("p");
        extra.className = "text-xs text-on-surface-variant mt-1";
        extra.textContent = [row.address, row.phone ? "Phone: " + row.phone : "", row.commodities_label ? "Commodities: " + row.commodities_label : ""]
          .filter(Boolean)
          .join(" · ");
        li.appendChild(extra);
      }

      var actions = document.createElement("div");
      actions.className = "flex items-center gap-3 mt-3 flex-wrap";
      if (row.source_url) {
        var link = document.createElement("a");
        link.className = "text-xs font-semibold text-primary";
        link.href = row.source_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "View Source";
        actions.appendChild(link);
      }
      if (row.directions_url) {
        var dir = document.createElement("a");
        dir.className = "text-xs font-semibold text-primary hover:underline flex items-center gap-1";
        dir.href = row.directions_url;
        dir.target = "_blank";
        dir.rel = "noopener noreferrer";
        dir.innerHTML = '<span class="material-symbols-outlined text-sm">directions</span> Directions';
        actions.appendChild(dir);
      }
      if (typeof row.latitude === "number" && typeof row.longitude === "number") {
        var locateBtn = document.createElement("button");
        locateBtn.type = "button";
        locateBtn.className = "text-xs font-semibold text-on-surface-variant hover:text-primary flex items-center gap-1";
        locateBtn.innerHTML = '<span class="material-symbols-outlined text-sm">my_location</span> Locate on map';
        (function (storageIndex) {
          locateBtn.addEventListener("click", function (e) {
            e.preventDefault();
            focusStorageMarker(storageIndex);
          });
        })(idx);
        actions.appendChild(locateBtn);
      }
      var bookBtn = document.createElement("button");
      bookBtn.type = "button";
      bookBtn.className = "text-xs font-bold text-white bg-primary hover:bg-primary-light px-3 py-1 rounded-lg transition-all ml-auto shadow-sm flex items-center gap-1";
      bookBtn.innerHTML = '<span class="material-symbols-outlined text-xs">payments</span> Book Demo Slot';
      bookBtn.addEventListener("click", function (e) {
        e.preventDefault();
        var paySec = document.querySelector('[aria-label="Demo payment"]');
        if (paySec) {
          paySec.scrollIntoView({ behavior: "smooth", block: "center" });
          paySec.classList.add("ring-2", "ring-primary", "shadow-xl");
          setTimeout(function () {
            paySec.classList.remove("ring-2", "ring-primary", "shadow-xl");
          }, 2500);
        }
      });
      actions.appendChild(bookBtn);
      if (actions.childNodes.length) {
        li.appendChild(actions);
      }
      listEl.appendChild(li);
    });
    renderStorageMap(rows, payload);
  }

  function focusStorageMarker(idx) {
    if (!storageMap || !storageMarkers[idx]) { return; }
    var marker = storageMarkers[idx];
    storageMap.setView(marker.getLatLng(), 14, { animate: true });
    marker.openPopup();
    var mapEl = document.getElementById("dash-storage-map");
    if (mapEl) {
      mapEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function renderStorageMap(rows, payload) {
    if (typeof L === "undefined") { return; }
    var mapEl = document.getElementById("dash-storage-map");
    if (!mapEl) { return; }

    // Gather rows that have coordinates
    var pinnable = rows.filter(function (r) {
      return typeof r.latitude === "number" && typeof r.longitude === "number"
          && isFinite(r.latitude) && isFinite(r.longitude);
    });

    if (!pinnable.length) {
      mapEl.classList.add("hidden");
      return;
    }

    mapEl.classList.remove("hidden");

    // Initialise or reuse map
    if (!storageMap) {
      storageMap = L.map("dash-storage-map");
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
        maxZoom: 18,
      }).addTo(storageMap);
    }

    // Clear previous markers
    storageMarkers.forEach(function (m) { m.remove(); });
    storageMarkers = [];

    var bounds = [];

    // Add farmer origin pin if available
    var farmerLoc = payload && payload.farmer_location;
    if (farmerLoc && typeof farmerLoc.latitude === "number" && typeof farmerLoc.longitude === "number") {
      var farmLat = farmerLoc.latitude;
      var farmLon = farmerLoc.longitude;
      var farmIcon = L.divIcon({
        className: "custom-farmer-pin",
        html: '<div style="background-color:#059669;color:#ffffff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,0.35);border:2px solid #ffffff;">F</div>',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -15]
      });
      var farmMarker = L.marker([farmLat, farmLon], { icon: farmIcon })
        .bindPopup("<b>Farm / Origin</b><br>" + (farmerLoc.name || payload.requested_location || "Farmer location"))
        .addTo(storageMap);
      storageMarkers.push(farmMarker);
      bounds.push([farmLat, farmLon]);
    }

    pinnable.forEach(function (row, idx) {
      var lat = row.latitude;
      var lng = row.longitude;
      var label = row.name || "Cold Storage " + (idx + 1);
      var capacity = row.capacity_mt ? " · " + row.capacity_mt + " MT" : "";
      var dist = "";
      if (row.road_distance_km !== null && row.road_distance_km !== undefined) {
        dist = " · " + row.road_distance_km + " km (road)";
      } else if (row.distance_km !== null && row.distance_km !== undefined) {
        dist = " · " + row.distance_km + " km (straight-line)";
      }
      var dirLink = row.directions_url ? "<br><a href='" + row.directions_url + "' target='_blank' rel='noopener' style='color:#075b43;font-weight:700;'>Get Directions ↗</a>" : "";
      var popup = "<b>#" + (idx + 1) + " " + label + "</b><br>"
        + (row.district || row.location || "") + dist + capacity + dirLink;

      var storageIcon = L.divIcon({
        className: "custom-storage-pin",
        html: '<div style="background-color:#d97706;color:#ffffff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid #ffffff;">' + (idx + 1) + '</div>',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
      });

      var marker = L.marker([lat, lng], { icon: storageIcon })
        .bindPopup(popup)
        .addTo(storageMap);
      storageMarkers.push(marker);
      bounds.push([lat, lng]);
    });

    if (bounds.length === 1) {
      storageMap.setView(bounds[0], 11);
    } else {
      storageMap.fitBounds(bounds, { padding: [35, 35] });
    }
    // Force redraw after reveal
    setTimeout(function () { storageMap.invalidateSize(); }, 120);
  }

  function search() {
    if (!window.CropMandiAPI || !CropMandiAPI.getColdStorageByLocation) {
      showError(ERROR_MESSAGE);
      return;
    }
    var location = selectedLocation();
    if (!location) {
      showError("Select a location first.");
      return;
    }
    var seq = ++requestSeq;
    setLoading(true);
    CropMandiAPI.getColdStorageByLocation(location, 5)
      .then(function (payload) {
        if (seq !== requestSeq) {
          return;
        }
        render(payload);
      })
      .catch(function () {
        if (seq !== requestSeq) {
          return;
        }
        showError(ERROR_MESSAGE);
      });
  }

  function init() {
    cropSelect = $("dash-storage-crop");
    dashCropSelect = $("dash-crop");
    locationSelect = $("dash-location");
    locationLabel = $("dash-storage-location-label");
    headingEl = $("dash-storage-heading");
    quantityInput = $("dash-storage-qty");
    searchButton = $("dash-storage-search");
    statusEl = $("dash-storage-status");
    errorEl = $("dash-storage-error");
    listEl = $("dash-storage-list");
    countEl = $("dash-storage-count");
    routingEl = $("dash-storage-routing");
    if (!searchButton || !listEl) {
      return;
    }
    if (dashCropSelect && cropSelect && !cropSelect.value) {
      cropSelect.value = dashCropSelect.value;
    }
    if (dashCropSelect && cropSelect) {
      dashCropSelect.addEventListener("change", function () {
        cropSelect.value = dashCropSelect.value;
      });
    }
    searchButton.addEventListener("click", function (event) {
      event.preventDefault();
      search();
    });
    if (locationSelect) {
      locationSelect.addEventListener("change", search);
      new MutationObserver(function () {
        if (locationSelect.value) {
          search();
        }
      }).observe(locationSelect, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
