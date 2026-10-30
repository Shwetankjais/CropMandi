/**
 * Dashboard commodity/location loader. Uses market-centre APIs for the
 * selected place. Does not invent location prices or location-name aliases.
 */
(function () {
  "use strict";

  var COFFEE_SERIES = [
    "Arabica Parchment",
    "Arabica Cherry",
    "Robusta Parchment",
    "Robusta Cherry",
  ];
  var PEPPER_SERIES = ["Cochin Garbled", "Cochin Ungarbled", "Sirsi"];
  var COFFEE_TYPE_ORDER = [
    "ARABICA PARCHMENT",
    "ARABICA CHERRY",
    "ROBUSTA PARCHMENT",
    "ROBUSTA CHERRY",
  ];
  var LOADING_MESSAGE = "Loading market prices...";
  var EMPTY_MESSAGE = "No verified price observations available for this location.";
  var ERROR_MESSAGE = "Unable to load market data. Please try again.";
  var COFFEE_UNIT = "Rs./50 Kg";
  var COFFEE_WARNING =
    "Unverified local market-centre data — not official Coffee Board data";

  var cropSelect;
  var locationSelect;
  var seriesSelect;
  var quantityInput;
  var refreshButton;
  var tableBody;
  var colSeries;
  var colLatest;
  var colAsOf;
  var tableStatus;
  var tableNote;
  var latestPriceEl;
  var latestMetaEl;
  var sourceNoteEl;
  var centresList;
  var centresLocationEl;
  var locationLabelEl;
  var bestApmcEl;
  var bestApmcPriceEl;
  var latestUnitEl;
  var recCropEl;
  var recVarietyEl;
  var requestSeq = 0;
  var lastAvailable = null;
  var lastCentres = null;
  var lastPrices = null;

  function $(id) {
    return document.getElementById(id);
  }

  function commodity() {
    return cropSelect && cropSelect.value ? cropSelect.value : "coffee";
  }

  function seriesForCommodity(code) {
    if (code === "pepper") return PEPPER_SERIES;
    if (code === "coffee") return COFFEE_SERIES;
    return [];
  }

  function fillSeriesOptions(callback) {
    if (!seriesSelect) {
      if (callback) callback();
      return;
    }
    var code = commodity();
    var previous = seriesSelect.value || localStorage.getItem("cropmandi_dash_variety") || "";

    if (code === "coffee" || code === "pepper") {
      var names = seriesForCommodity(code);
      seriesSelect.innerHTML = "";
      names.forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        seriesSelect.appendChild(opt);
      });
      if (names.indexOf(previous) !== -1) {
        seriesSelect.value = previous;
      } else if (names.length > 0) {
        seriesSelect.value = names[0];
      }
      if (callback) callback();
      return;
    }

    if (window.CropMandiAPI && CropMandiAPI.getCommodityOptions) {
      CropMandiAPI.getCommodityOptions(code)
        .then(function (res) {
          var names = (res && res.varieties) || ["LOCAL"];
          seriesSelect.innerHTML = "";
          names.forEach(function (name) {
            var opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            seriesSelect.appendChild(opt);
          });
          if (names.indexOf(previous) !== -1) {
            seriesSelect.value = previous;
          } else if (names.length > 0) {
            seriesSelect.value = names[0];
          }
          if (callback) callback();
        })
        .catch(function () {
          if (callback) callback();
        });
    } else {
      if (callback) callback();
    }
  }

  function normalizeTypeKey(value) {
    return String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toUpperCase();
  }

  function isNumericOtValue(typeName) {
    return /^\d+(\.\d+)?$/.test(String(typeName || "").trim());
  }

  function coffeeCoreKey(typeName) {
    var key = normalizeTypeKey(typeName);
    var i;
    for (i = 0; i < COFFEE_TYPE_ORDER.length; i += 1) {
      if (key === COFFEE_TYPE_ORDER[i] || key.indexOf(COFFEE_TYPE_ORDER[i] + " ") === 0) {
        return COFFEE_TYPE_ORDER[i];
      }
    }
    return "";
  }

  function displayTypeName(code, typeName) {
    if (code !== "coffee") {
      return typeName;
    }
    var key = normalizeTypeKey(typeName);
    var i;
    for (i = 0; i < COFFEE_TYPE_ORDER.length; i += 1) {
      if (key === COFFEE_TYPE_ORDER[i]) {
        return COFFEE_SERIES[i];
      }
    }
    return typeName;
  }

  function unitLabel(code, payload) {
    if (payload && payload.unit) {
      return payload.unit;
    }
    if (code === "coffee") {
      return COFFEE_UNIT;
    }
    return "";
  }

  function setLoading(isLoading) {
    tableStatus.textContent = isLoading ? LOADING_MESSAGE : "";
    tableStatus.classList.toggle("hidden", !isLoading);
    if (refreshButton) {
      refreshButton.disabled = isLoading;
      refreshButton.classList.toggle("opacity-70", isLoading);
    }
    if (locationSelect) {
      locationSelect.disabled = isLoading && !locationSelect.value;
    }
    if (isLoading) {
      tableBody.innerHTML =
        '<tr><td colspan="4" class="px-3 py-4 text-center text-on-surface-variant">' +
        LOADING_MESSAGE +
        "</td></tr>";
      latestPriceEl.textContent = "…";
      latestMetaEl.textContent = "Loading";
      sourceNoteEl.textContent = "";
      if (centresList) {
        centresList.innerHTML = "";
      }
    }
  }

  function showError(message) {
    tableBody.innerHTML =
      '<tr><td colspan="4" class="px-3 py-4 text-center text-error">' +
      message +
      "</td></tr>";
    latestPriceEl.textContent = "Data unavailable";
    latestMetaEl.textContent = "Unavailable";
    sourceNoteEl.textContent = message;
    tableNote.textContent = "";
    updateOutlookSelection();
    setOutlookUnavailable();
    if (centresList) {
      centresList.innerHTML = "";
    }
  }

  function showEmpty() {
    tableBody.innerHTML =
      '<tr><td colspan="4" class="px-3 py-4 text-center text-on-surface-variant">' +
      EMPTY_MESSAGE +
      "</td></tr>";
    latestPriceEl.textContent = "Data unavailable";
    latestMetaEl.textContent = EMPTY_MESSAGE;
    updateOutlookSelection();
    setOutlookUnavailable();
  }

  function collectTypes(code, centres) {
    var seen = {};
    var types = [];
    (centres || []).forEach(function (row) {
      (row.types || []).forEach(function (typeName) {
        if (!typeName || isNumericOtValue(typeName)) {
          return;
        }
        var key = normalizeTypeKey(typeName);
        if (!seen[key]) {
          seen[key] = typeName;
          types.push(typeName);
        }
      });
    });
    if (code !== "coffee") {
      types.sort(function (a, b) {
        return a.localeCompare(b);
      });
      return types;
    }
    var ordered = [];
    COFFEE_TYPE_ORDER.forEach(function (core) {
      types.forEach(function (typeName) {
        if (normalizeTypeKey(typeName) === core) {
          ordered.push(typeName);
        }
      });
    });
    types.forEach(function (typeName) {
      if (ordered.indexOf(typeName) === -1) {
        ordered.push(typeName);
      }
    });
    return ordered;
  }

  function latestDateForType(centres, typeName) {
    var wanted = normalizeTypeKey(typeName);
    var latest = "";
    (centres || []).forEach(function (row) {
      var hasType = (row.types || []).some(function (item) {
        return normalizeTypeKey(item) === wanted;
      });
      if (!hasType) {
        return;
      }
      if (row.date_to && (!latest || row.date_to > latest)) {
        latest = row.date_to;
      }
    });
    return latest;
  }

  function cropLabel() {
    if (!cropSelect || !cropSelect.options.length) {
      return "";
    }
    var option = cropSelect.options[cropSelect.selectedIndex];
    return option ? option.textContent : "";
  }

  function numericPrice(value) {
    var n = typeof value === "number" ? value : Number(value);
    return Number.isFinite(n) && n > 0 ? n : NaN;
  }

  function pepperMatchesSelection(selectedKey, obs) {
    var typeKey = normalizeTypeKey(obs && obs.type);
    var marketKey = normalizeTypeKey(obs && obs.market_centre);
    var locKey = normalizeTypeKey(obs && obs.location);
    if (!selectedKey) {
      return true;
    }
    if (typeKey === selectedKey) {
      return true;
    }
    if (selectedKey.indexOf("UNGARB") !== -1) {
      return typeKey.indexOf("UNGARB") !== -1;
    }
    if (selectedKey.indexOf("GARBLED") !== -1 || selectedKey.indexOf("GARBALED") !== -1) {
      return (
        (typeKey.indexOf("GARBLED") !== -1 || typeKey.indexOf("GARBALED") !== -1) &&
        typeKey.indexOf("UNGARB") === -1
      );
    }
    if (selectedKey === "SIRSI") {
      return marketKey.indexOf("SIRSI") !== -1 || locKey === "SIRSI";
    }
    if (selectedKey === "WHITE") {
      return typeKey === "WHITE";
    }
    return false;
  }

  function observationsForSelection(code, pricesPayload) {
    var observations = (pricesPayload && pricesPayload.observations) || [];
    var selectedKey = normalizeTypeKey(seriesSelect && seriesSelect.value);
    if (code === "coffee") {
      if (!selectedKey) {
        return observations;
      }
      return observations.filter(function (obs) {
        return normalizeTypeKey(obs.type) === selectedKey;
      });
    }
    if (code !== "pepper") {
      return observations;
    }
    var matched = observations.filter(function (obs) {
      return pepperMatchesSelection(selectedKey, obs);
    });
    if (matched.length) {
      return matched;
    }
    // Local pepper types are UnGarbaled/White, not Cochin Garbled. Use real location rows.
    if (!selectedKey || selectedKey.indexOf("GARB") !== -1 || selectedKey === "WHITE") {
      return observations;
    }
    return matched;
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = value || "";
    }
  }

  function renderPriceInsights(rows, selectedObs, pricesPayload) {
    var dateEl = document.getElementById("dash-price-date");
    var sourceEl = document.getElementById("dash-price-source");
    var statusEl = document.getElementById("dash-price-status");
    if (dateEl) {
      dateEl.textContent = (selectedObs && selectedObs.date) || "—";
    }
    if (sourceEl) {
      sourceEl.textContent =
        (selectedObs && selectedObs.source) ||
        (pricesPayload && (pricesPayload.source_workbook || pricesPayload.provenance)) ||
        "—";
    }
    if (statusEl) {
      if (selectedObs && selectedObs.official) {
        statusEl.textContent = "Verified";
      } else if (selectedObs && selectedObs.data_status) {
        statusEl.textContent = String(selectedObs.data_status).replace(/_/g, " ");
      } else {
        statusEl.textContent = "Observed";
      }
    }
  }

  function setOutlookUnavailable() {
    if (latestPriceEl) {
      latestPriceEl.textContent = "Data unavailable";
    }
    if (latestUnitEl) {
      latestUnitEl.textContent = "";
    }
    if (bestApmcEl) {
      bestApmcEl.textContent = "Data unavailable";
    }
    if (bestApmcPriceEl) {
      bestApmcPriceEl.textContent = "";
    }
    setText("dash-price-date", "—");
    setText("dash-price-source", "—");
    setText("dash-price-status", "");
  }

  function updateOutlookSelection() {
    if (recCropEl) {
      recCropEl.textContent = cropLabel() || "—";
    }
    if (recVarietyEl) {
      recVarietyEl.textContent = (seriesSelect && seriesSelect.value) || "—";
    }
  }

  function updateBestApmc(code, pricesPayload) {
    var rows = observationsForSelection(code, pricesPayload);
    var best = null;
    rows.forEach(function (obs) {
      var price = numericPrice(obs.price);
      if (!Number.isFinite(price)) {
        return;
      }
      if (!best || price > best.price) {
        best = { market_centre: obs.market_centre, price: price };
      }
    });
    if (!best) {
      if (bestApmcEl) {
        bestApmcEl.textContent = "Data unavailable";
      }
      if (bestApmcPriceEl) {
        bestApmcPriceEl.textContent = "";
      }
      return;
    }
    var unit = unitLabel(code, pricesPayload);
    if (bestApmcEl) {
      bestApmcEl.textContent = best.market_centre || "Data unavailable";
    }
    if (bestApmcPriceEl) {
      bestApmcPriceEl.textContent =
        "₹" +
        Number(best.price).toLocaleString("en-IN") +
        (unit ? " · " + unit : "");
    }
  }

  function applyStatusNotes(code, pricesPayload) {
    if (sourceNoteEl) {
      var parts = [];
      if (pricesPayload && pricesPayload.provenance) {
        parts.push(pricesPayload.provenance);
      }
      if (pricesPayload && pricesPayload.unit) {
        parts.push(pricesPayload.unit);
      }
      sourceNoteEl.textContent = parts.join(" · ");
    }
    if (tableNote) {
      tableNote.textContent = "";
    }
  }

  function renderCentres(locationName, centresPayload) {
    var location = (centresPayload && centresPayload.location) || locationName || "";
    if (locationLabelEl) {
      locationLabelEl.textContent = location;
    }
    if (centresLocationEl) {
      centresLocationEl.textContent = location ? "Location: " + location : "";
    }
    centresList.innerHTML = "";
    var rows = (centresPayload && centresPayload.centres) || [];
    if (!rows.length) {
      var empty = document.createElement("li");
      empty.className = "text-on-surface-variant";
      empty.textContent = "No market centres mapped to this location.";
      centresList.appendChild(empty);
      return;
    }
    rows.forEach(function (row) {
      var li = document.createElement("li");
      li.textContent = row.raw_market_centre || "";
      if (row.ambiguous && row.also_mapped_to && row.also_mapped_to.length) {
        var extra = document.createElement("span");
        extra.className = "block text-label-sm font-label-sm text-on-surface-variant";
        extra.textContent = "Also mapped to: " + row.also_mapped_to.join(", ");
        li.appendChild(extra);
      }
      centresList.appendChild(li);
    });
  }

  function renderTable(code, pricesPayload) {
    var observations = (pricesPayload && pricesPayload.observations) || [];
    var unit = unitLabel(code, pricesPayload);
    colSeries.textContent = "Market Centre";
    colLatest.textContent = unit ? "Latest (" + unit + ")" : "Latest";
    colAsOf.textContent = "As of";
    tableBody.innerHTML = "";

    if (!observations.length) {
      showEmpty();
      return;
    }

    // Filter observations by selected variety for Coffee
    var filteredObservations = observations;
    if (code === "coffee") {
      var selectedKey = normalizeTypeKey(seriesSelect.value);
      if (selectedKey) {
        filteredObservations = observations.filter(function (obs) {
          return normalizeTypeKey(obs.type) === selectedKey;
        });
      }
    }

    if (!filteredObservations.length) {
      showEmpty();
      return;
    }

    var latestByCentre = {};
    filteredObservations.forEach(function (obs) {
      var name = obs.market_centre || "Unknown";
      var prev = latestByCentre[name];
      if (!prev || String(obs.date || "") > String(prev.date || "")) {
        latestByCentre[name] = obs;
      }
    });
    var comparisonRows = Object.keys(latestByCentre).map(function (name) {
      return latestByCentre[name];
    });
    comparisonRows.sort(function (a, b) {
      return numericPrice(b.price) - numericPrice(a.price);
    });

    comparisonRows.forEach(function (obs) {
      var tr = document.createElement("tr");
      tr.className = "border-b border-outline-variant/10";

      var tdName = document.createElement("td");
      tdName.className = "px-3 py-2 text-on-background";
      tdName.textContent = obs.market_centre || "Unknown";

      var tdPrice = document.createElement("td");
      tdPrice.className = "px-3 py-2 text-right text-on-background font-semibold";
      if (Number.isFinite(obs.price) && obs.price > 0) {
        tdPrice.textContent = "₹" + Number(obs.price).toLocaleString("en-IN");
      } else {
        tdPrice.textContent = "—";
      }

      var tdDate = document.createElement("td");
      tdDate.className = "px-3 py-2 text-right text-on-surface-variant";
      tdDate.textContent = obs.date || "—";

      var tdSource = document.createElement("td");
      tdSource.className = "px-3 py-2 text-on-surface-variant";
      tdSource.textContent = obs.source || "—";

      tr.appendChild(tdName);
      tr.appendChild(tdPrice);
      tr.appendChild(tdDate);
      tr.appendChild(tdSource);
      tableBody.appendChild(tr);
    });
  }

  function renderSelected(code, pricesPayload) {
    updateOutlookSelection();
    var filteredObservations = observationsForSelection(code, pricesPayload);
    if (!filteredObservations.length) {
      setOutlookUnavailable();
      if (latestMetaEl) {
        latestMetaEl.textContent = "No data for selected variety";
      }
      return;
    }

    var unit = unitLabel(code, pricesPayload);
    var selectedObs = filteredObservations[0];
    var location = (pricesPayload && pricesPayload.location) || "";
    var selectedType = displayTypeName(code, selectedObs.type);

    var price = numericPrice(selectedObs.price);
    if (Number.isFinite(price)) {
      latestPriceEl.textContent = "₹" + Number(price).toLocaleString("en-IN");
    } else {
      latestPriceEl.textContent = "Data unavailable";
    }
    if (latestUnitEl) {
      latestUnitEl.textContent = unit || "";
    }

    latestMetaEl.textContent =
      selectedType +
      (unit ? " · " + unit : "") +
      " · " +
      location +
      (selectedObs.date ? " · as of " + selectedObs.date : "");
    updateBestApmc(code, pricesPayload);
    renderPriceInsights(filteredObservations, selectedObs, pricesPayload);
  }

  function hasVerifiedObservations(pricesPayload) {
    var observations = (pricesPayload && pricesPayload.observations) || [];
    return observations.some(function (obs) {
      return Number.isFinite(obs.price) && obs.price > 0;
    });
  }

  function loadLocations() {
    if (!window.CropMandiAPI || !CropMandiAPI.getMarkets) {
      showError(ERROR_MESSAGE);
      return;
    }
    var code = commodity();
    var seq = ++requestSeq;
    var previous = locationSelect.value || localStorage.getItem("cropmandi_dash_location") || "";
    setLoading(true);
    locationSelect.disabled = true;
    
    // For Coffee, we need to filter locations by variety
    if (code === "coffee") {
      loadLocationsForCoffeeVariety(seq, previous);
    } else if (code === "pepper") {
      // For Pepper, use existing behavior
      loadLocationsForCommodity(code, seq, previous);
    } else {
      // For Tomato, Potato, Maize, Paddy
      loadLocationsForVegetable(code, seq, previous);
    }
  }

  function loadLocationsForVegetable(code, seq, previous) {
    if (!window.CropMandiAPI || !CropMandiAPI.getCommodityOptions) {
      showError(ERROR_MESSAGE);
      return;
    }
    CropMandiAPI.getCommodityOptions(code)
      .then(function (options) {
        if (seq !== requestSeq) return;
        var locations = options.locations || [];
        var markets = options.markets || [];
        locationSelect.innerHTML = "";
        if (!locations.length) {
          showEmpty();
          return;
        }
        locations.forEach(function (loc) {
          var opt = document.createElement("option");
          opt.value = loc.market;
          opt.textContent = loc.market + (loc.district ? " (" + loc.district + ")" : "");
          locationSelect.appendChild(opt);
        });
        if (previous && markets.indexOf(previous) !== -1) {
          locationSelect.value = previous;
        } else if (markets.length > 0) {
          locationSelect.value = markets[0];
        }
        locationSelect.disabled = false;
        if (locationSelect.value) {
          localStorage.setItem("cropmandi_dash_location", locationSelect.value);
        }
        loadLocationData(seq);
      })
      .catch(function () {
        if (seq !== requestSeq) return;
        showError(ERROR_MESSAGE);
      });
  }

  function loadLocationsForCommodity(code, seq, previous) {
    CropMandiAPI.getMarkets(code)
      .then(function (payload) {
        if (seq !== requestSeq) {
          return;
        }
        var names = ((payload && payload.locations) || [])
          .map(function (row) {
            return row && row.name;
          })
          .filter(Boolean);
        locationSelect.innerHTML = "";
        if (!names.length) {
          locationSelect.disabled = false;
          showError(ERROR_MESSAGE);
          return;
        }
        names.forEach(function (name) {
          var opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          locationSelect.appendChild(opt);
        });
        if (names.indexOf(previous) !== -1) {
          locationSelect.value = previous;
        } else if (names.indexOf("Sakleshpur") !== -1) {
          locationSelect.value = "Sakleshpur";
        } else {
          locationSelect.value = names[0];
        }
        locationSelect.disabled = false;
        // Save location to localStorage
        if (locationSelect.value) {
          localStorage.setItem("cropmandi_dash_location", locationSelect.value);
        }
        loadLocationData(seq);
      })
      .catch(function () {
        if (seq !== requestSeq) {
          return;
        }
        var fallbacks = code === "pepper" ? ["Cochin", "Sirsi", "Wayanad", "Idukki"] : ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan"];
        locationSelect.innerHTML = "";
        fallbacks.forEach(function (name) {
          var opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          locationSelect.appendChild(opt);
        });
        locationSelect.value = fallbacks[0];
        locationSelect.disabled = false;
        setLoading(false);
        loadLocationData(seq);
      });
  }

  function loadLocationsForCoffeeVariety(seq, previous) {
    var selectedVariety = seriesSelect.value;
    var wantedKey = normalizeTypeKey(selectedVariety);
    
    CropMandiAPI.getMarkets("coffee")
      .then(function (payload) {
        if (seq !== requestSeq) {
          return;
        }
        var allLocations = ((payload && payload.locations) || [])
          .map(function (row) {
            return row && row.name;
          })
          .filter(Boolean);
        
        if (!allLocations.length) {
          locationSelect.innerHTML = "";
          locationSelect.disabled = false;
          showError(ERROR_MESSAGE);
          return;
        }
        
        // Filter locations by checking which ones have the selected variety
        var locationPromises = allLocations.map(function (location) {
          return CropMandiAPI.getMarketAvailable("coffee", location)
            .then(function (available) {
              if (!available || !available.centres) {
                return null;
              }
              // Check if this location has the selected variety
              var hasVariety = available.centres.some(function (centre) {
                return (centre.types || []).some(function (typeName) {
                  return normalizeTypeKey(typeName) === wantedKey;
                });
              });
              return hasVariety ? location : null;
            })
            .catch(function () {
              return null;
            });
        });
        
        return Promise.all(locationPromises).then(function (results) {
          return results.filter(Boolean);
        });
      })
      .then(function (validLocations) {
        if (seq !== requestSeq) {
          return;
        }
        locationSelect.innerHTML = "";
        
        if (!validLocations || !validLocations.length) {
          validLocations = allLocations && allLocations.length ? allLocations : ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan", "Kushalnagar"];
        }
        
        validLocations.forEach(function (name) {
          var opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          locationSelect.appendChild(opt);
        });
        
        // Try to keep previous selection if it's still valid
        if (validLocations.indexOf(previous) !== -1) {
          locationSelect.value = previous;
        } else if (validLocations.indexOf("Sakleshpur") !== -1) {
          locationSelect.value = "Sakleshpur";
        } else {
          locationSelect.value = validLocations[0];
        }
        
        locationSelect.disabled = false;
        // Save location to localStorage
        if (locationSelect.value) {
          localStorage.setItem("cropmandi_dash_location", locationSelect.value);
        }
        loadLocationData(seq);
      })
      .catch(function () {
        if (seq !== requestSeq) {
          return;
        }
        var fallbacks = ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan"];
        locationSelect.innerHTML = "";
        fallbacks.forEach(function (name) {
          var opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          locationSelect.appendChild(opt);
        });
        locationSelect.value = fallbacks[0];
        locationSelect.disabled = false;
        setLoading(false);
        loadLocationData(seq);
      });
  }

  function loadLocationData(existingSeq) {
    var code = commodity();
    var location = locationSelect.value;
    if (!location) {
      return;
    }
    var seq = existingSeq || ++requestSeq;
    setLoading(true);

    if (code !== "coffee" && code !== "pepper") {
      if (!window.CropMandiAPI || !CropMandiAPI.getAnalytics) {
        showError(ERROR_MESSAGE);
        return;
      }
      CropMandiAPI.getAnalytics(code, location, 30)
        .then(function (payload) {
          if (seq !== requestSeq) return;
          setLoading(false);
          tableStatus.classList.add("hidden");
          renderVegetableData(code, location, payload);
        })
        .catch(function () {
          if (seq !== requestSeq) return;
          setLoading(false);
          tableStatus.classList.add("hidden");
          showError(ERROR_MESSAGE);
        });
      return;
    }

    if (!window.CropMandiAPI || !CropMandiAPI.getMarketCentres || !CropMandiAPI.getMarketPrices) {
      showError(ERROR_MESSAGE);
      return;
    }
    Promise.all([
      CropMandiAPI.getMarketCentres(code, location),
      CropMandiAPI.getMarketPrices(code, location),
    ])
      .then(function (results) {
        if (seq !== requestSeq) {
          return;
        }
        var centresPayload = results[0];
        var pricesPayload = results[1];
        setLoading(false);
        tableStatus.classList.add("hidden");
        lastCentres = centresPayload;
        lastPrices = pricesPayload;
        renderCentres(location, centresPayload);
        applyStatusNotes(code, pricesPayload);
        if (!pricesPayload || !pricesPayload.observations || !pricesPayload.observations.length) {
          showEmpty();
          return;
        }
        renderTable(code, pricesPayload);
        renderSelected(code, pricesPayload);
      })
      .catch(function () {
        if (seq !== requestSeq) {
          return;
        }
        setLoading(false);
        tableStatus.classList.add("hidden");
        showError(ERROR_MESSAGE);
      });
  }

  function renderVegetableData(code, location, payload) {
    if (!payload || !payload.available) {
      showEmpty();
      return;
    }
    var latest = payload.latest || {};
    var price = latest.price;
    var unit = latest.unit || "Rs./Quintal";
    var date = latest.date;

    if (latestPriceEl) {
      latestPriceEl.textContent = Number.isFinite(price) ? "₹" + Number(price).toLocaleString("en-IN") : "—";
    }
    if (latestUnitEl) {
      latestUnitEl.textContent = unit;
    }
    if (latestMetaEl) {
      latestMetaEl.textContent = (seriesSelect ? seriesSelect.value : code.toUpperCase()) + " · " + unit + " · " + location + (date ? " · as of " + date : "");
    }
    var priceDateEl = $("dash-price-date");
    if (priceDateEl) {
      priceDateEl.textContent = date || "—";
    }
    var priceSourceEl = $("dash-price-source");
    if (priceSourceEl) {
      priceSourceEl.textContent = "AGMARKNET 2025-2026 dataset";
    }
    if (locationLabelEl) {
      locationLabelEl.textContent = location;
    }
    if (recCropEl) {
      recCropEl.textContent = code.charAt(0).toUpperCase() + code.slice(1);
    }
    if (recVarietyEl) {
      recVarietyEl.textContent = (seriesSelect ? seriesSelect.value : "LOCAL");
    }

    var comparisons = payload.market_comparison || [];
    tableBody.innerHTML = "";
    if (comparisons.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="4" class="px-3 py-4 text-center text-on-surface-variant">No comparison markets found</td></tr>';
    } else {
      comparisons.forEach(function (row) {
        var tr = document.createElement("tr");
        tr.className = "border-b border-outline-variant/10";
        var tdName = document.createElement("td");
        tdName.className = "px-3 py-2 text-on-background font-medium";
        tdName.textContent = row.centre + (row.district ? " (" + row.district + ")" : "");

        var tdPrice = document.createElement("td");
        tdPrice.className = "px-3 py-2 text-right text-on-background font-semibold";
        tdPrice.textContent = Number.isFinite(row.price) ? "₹" + Number(row.price).toLocaleString("en-IN") : "—";

        var tdDate = document.createElement("td");
        tdDate.className = "px-3 py-2 text-right text-on-surface-variant";
        tdDate.textContent = row.date || "—";

        var tdSource = document.createElement("td");
        tdSource.className = "px-3 py-2 text-on-surface-variant";
        tdSource.textContent = "AGMARKNET";

        tr.appendChild(tdName);
        tr.appendChild(tdPrice);
        tr.appendChild(tdDate);
        tr.appendChild(tdSource);
        tableBody.appendChild(tr);
      });

      var best = comparisons[0];
      if (bestApmcEl) {
        bestApmcEl.textContent = best.centre + (best.district ? " (" + best.district + ")" : "");
      }
      if (bestApmcPriceEl) {
        bestApmcPriceEl.textContent = "₹" + Number(best.price).toLocaleString("en-IN") + " · " + (best.unit || "Rs./Quintal");
      }
    }

    if (centresList) {
      centresList.innerHTML = "";
      var li = document.createElement("li");
      li.className = "truncate text-on-surface-variant";
      li.textContent = location + " (Direct APMC Mandi)";
      centresList.appendChild(li);
    }
    if (centresLocationEl) {
      centresLocationEl.textContent = "Mandi: " + location;
    }
  }

  function refreshSelectedHighlight() {
    if (!lastPrices) {
      return;
    }
    renderTable(commodity(), lastPrices);
    renderSelected(commodity(), lastPrices);
  }

  function init() {
    cropSelect = $("dash-crop");
    locationSelect = $("dash-location");
    seriesSelect = $("dash-series");
    quantityInput = $("dash-quantity");
    refreshButton = $("dash-refresh");
    tableBody = $("dash-price-rows");
    colSeries = $("dash-col-series");
    colLatest = $("dash-col-latest");
    colAsOf = $("dash-col-asof");
    tableStatus = $("dash-table-status");
    tableNote = $("dash-table-note");
    latestPriceEl = $("dash-latest-price");
    latestMetaEl = $("dash-latest-meta");
    latestUnitEl = $("dash-latest-unit");
    sourceNoteEl = $("dash-source-note");
    centresList = $("dash-centres");
    centresLocationEl = $("dash-centres-location");
    locationLabelEl = $("dash-location-label");
    bestApmcEl = $("dash-best-apmc");
    bestApmcPriceEl = $("dash-best-apmc-price");
    recCropEl = $("dash-rec-crop");
    recVarietyEl = $("dash-rec-variety");
    if (!cropSelect || !locationSelect || !tableBody) {
      return;
    }
    
    // Populate the commodity dropdown with all 6 supported commodities
    var commodities = [
      { value: "coffee", label: "Coffee" },
      { value: "pepper", label: "Black Pepper" },
      { value: "potato", label: "Potato" },
      { value: "tomato", label: "Tomato" },
      { value: "maize", label: "Maize" },
      { value: "paddy", label: "Paddy" },
    ];
    cropSelect.innerHTML = "";
    commodities.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c.value;
      opt.textContent = c.label;
      cropSelect.appendChild(opt);
    });
    
    // Restore saved state from localStorage
    var savedCommodity = localStorage.getItem("cropmandi_dash_commodity");
    var validCodes = ["coffee", "pepper", "potato", "tomato", "maize", "paddy"];
    if (savedCommodity && validCodes.indexOf(savedCommodity) !== -1) {
      cropSelect.value = savedCommodity;
    } else {
      cropSelect.value = "coffee";
    }

    // Set default target prediction date if empty
    var dateInput = $("dash-date");
    if (dateInput && !dateInput.value) {
      var tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      dateInput.value = tomorrow.toISOString().split("T")[0];
    }
    
    // Fill series options based on restored commodity
    fillSeriesOptions(function () {
      var savedVariety = localStorage.getItem("cropmandi_dash_variety");
      if (savedVariety) {
        for (var i = 0; i < seriesSelect.options.length; i++) {
          if (seriesSelect.options[i].value === savedVariety) {
            seriesSelect.value = savedVariety;
            break;
          }
        }
      }
    });
    
    var savedQuantity = localStorage.getItem("cropmandi_dash_quantity");
    if (savedQuantity && quantityInput) {
      quantityInput.value = savedQuantity;
    } else if (quantityInput) {
      quantityInput.value = "50";
    }
    
    function persistDashboardSelection() {
      if (cropSelect && cropSelect.value) {
        localStorage.setItem("cropmandi_dash_commodity", cropSelect.value);
      }
      if (seriesSelect && seriesSelect.value) {
        localStorage.setItem("cropmandi_dash_variety", seriesSelect.value);
      }
      if (locationSelect && locationSelect.value) {
        localStorage.setItem("cropmandi_dash_location", locationSelect.value);
      }
      if (quantityInput && quantityInput.value) {
        localStorage.setItem("cropmandi_dash_quantity", quantityInput.value);
      }
    }

    persistDashboardSelection();
    window.addEventListener("pagehide", persistDashboardSelection);

    cropSelect.addEventListener("change", function () {
      localStorage.setItem("cropmandi_dash_commodity", cropSelect.value);
      fillSeriesOptions(function () {
        persistDashboardSelection();
        updateOutlookSelection();
        loadLocations();
      });
    });
      fillSeriesOptions();
      persistDashboardSelection();
      updateOutlookSelection();
      loadLocations();
    });
    locationSelect.addEventListener("change", function () {
      // Save location to localStorage for My Crops to use
      if (locationSelect.value) {
        localStorage.setItem("cropmandi_dash_location", locationSelect.value);
      }
      loadLocationData();
    });
    seriesSelect.addEventListener("change", function () {
      // Save variety to localStorage
      localStorage.setItem("cropmandi_dash_variety", seriesSelect.value);
      updateOutlookSelection();
      // For Coffee, reload locations when variety changes
      if (commodity() === "coffee") {
        loadLocations();
      } else {
        // For Pepper, just refresh the highlight
        refreshSelectedHighlight();
      }
    });
    if (quantityInput) {
      quantityInput.addEventListener("change", function () {
        // Save quantity to localStorage
        localStorage.setItem("cropmandi_dash_quantity", quantityInput.value);
      });
    }
    if (refreshButton) {
      refreshButton.addEventListener("click", function (event) {
        event.preventDefault();
        loadLocationData();
      });
    }
    updateOutlookSelection();
    loadLocations();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
