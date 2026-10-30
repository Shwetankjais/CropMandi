/**
 * Farmer-facing dashboard greeting, weather, alerts, and saved predictions.
 */
(function (global) {
  "use strict";

  var ALERTS_KEY = "cropmandi_alerts";
  var PREDICTIONS_KEY = "cropmandi_saved_predictions";
  var lastWeatherSeq = 0;

  function $(id) {
    return document.getElementById(id);
  }

  function greetingPhrase(date) {
    var hour = date.getHours();
    if (hour >= 5 && hour < 12) {
      return "Good morning";
    }
    if (hour >= 12 && hour < 17) {
      return "Good afternoon";
    }
    if (hour >= 17 && hour < 21) {
      return "Good evening";
    }
    return "Good night";
  }

  function applyGreeting() {
    var el = $("dash-greeting");
    if (!el) {
      return;
    }
    var name = window.CropMandiAuth ? CropMandiAuth.firstName() : "Hemalatha";
    el.textContent = greetingPhrase(new Date()) + ", " + name;
  }

  function readList(key) {
    try {
      var raw = localStorage.getItem(key);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function writeList(key, list) {
    localStorage.setItem(key, JSON.stringify(list));
  }

  function selectedContext() {
    var cropEl = $("dash-crop");
    var seriesEl = $("dash-series");
    var locationEl = $("dash-location");
    var cropValue = cropEl ? cropEl.value : "";
    var cropLabel = cropEl && cropEl.options[cropEl.selectedIndex]
      ? cropEl.options[cropEl.selectedIndex].textContent
      : cropValue;
    return {
      crop: cropValue,
      cropLabel: cropLabel,
      variety: seriesEl ? seriesEl.value : "",
      location: locationEl ? locationEl.value : "",
    };
  }

  function currentPriceText() {
    var el = $("dash-latest-price");
    return el ? String(el.textContent || "").trim() : "";
  }

  function predictedPriceText() {
    var el = $("dash-est-next-price");
    return el ? String(el.textContent || "").trim() : "";
  }

  function setActionFeedback(message, isError) {
    var el = $("dash-action-feedback");
    if (!el) {
      return;
    }
    el.textContent = message || "";
    el.classList.toggle("hidden", !message);
    el.classList.toggle("text-error", !!isError);
    el.classList.toggle("text-primary", !isError);
  }

  /* WMO weather code → human-readable description mapping */
  var WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Rain showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm"
  };

  function setWeatherUI(temp, desc, humidity, locationName) {
    var tempEl = $("dash-weather-temp");
    var descEl = $("dash-weather-desc");
    var humEl  = $("dash-weather-humidity");
    var noteEl = $("dash-weather-note");
    var iconEl = $("dash-weather-icon");
    if (tempEl) tempEl.textContent = temp !== null ? Math.round(Number(temp)) + "°C" : "";
    if (descEl) descEl.textContent = desc || "—";
    if (humEl)  humEl.textContent  = humidity !== null ? "💧 " + humidity + "% humidity" : "";
    if (noteEl) noteEl.textContent = locationName ? "📍 " + locationName : "";
    /* Update weather icon emoji based on description */
    if (iconEl) {
      var d = (desc || "").toLowerCase();
      var emoji = "🌤️";
      if (d.indexOf("clear") !== -1 || d.indexOf("sunny") !== -1) emoji = "☀️";
      else if (d.indexOf("overcast") !== -1 || d.indexOf("cloudy") !== -1) emoji = "☁️";
      else if (d.indexOf("partly") !== -1 || d.indexOf("mainly clear") !== -1) emoji = "🌤️";
      else if (d.indexOf("thunder") !== -1) emoji = "⛈️";
      else if (d.indexOf("heavy rain") !== -1 || d.indexOf("violent") !== -1) emoji = "🌧️";
      else if (d.indexOf("rain") !== -1 || d.indexOf("shower") !== -1 || d.indexOf("drizzle") !== -1) emoji = "🌦️";
      else if (d.indexOf("snow") !== -1) emoji = "❄️";
      else if (d.indexOf("fog") !== -1) emoji = "🌫️";
      else if (d.indexOf("wind") !== -1) emoji = "💨";
      iconEl.textContent = emoji;
    }
  }

  function weatherUnavailable(reason) {
    var descEl = $("dash-weather-desc");
    var noteEl = $("dash-weather-note");
    var tempEl = $("dash-weather-temp");
    var humEl  = $("dash-weather-humidity");
    if (tempEl) tempEl.textContent = "";
    if (humEl)  humEl.textContent  = "";
    if (descEl) descEl.textContent = reason || "Weather unavailable";
    if (noteEl) noteEl.textContent = "Enable the backend or check internet access";
  }

  /* Open-Meteo geocoding + weather fallback (free, no key needed) */
  function loadWeatherFromOpenMeteo(locationName, seq) {
    var geocodeUrl =
      "https://geocoding-api.open-meteo.com/v1/search?name=" +
      encodeURIComponent(locationName) +
      "&count=1&language=en&format=json";

    fetch(geocodeUrl)
      .then(function (r) { return r.json(); })
      .then(function (geo) {
        if (seq !== lastWeatherSeq) return;
        var results = geo && geo.results;
        if (!results || !results.length) {
          weatherUnavailable("Location not found");
          return;
        }
        var place = results[0];
        var lat = place.latitude;
        var lon = place.longitude;
        var displayName = place.name + (place.admin1 ? ", " + place.admin1 : "");

        var weatherUrl =
          "https://api.open-meteo.com/v1/forecast?latitude=" + lat +
          "&longitude=" + lon +
          "&current=temperature_2m,relative_humidity_2m,weathercode" +
          "&timezone=auto&forecast_days=1";

        return fetch(weatherUrl)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (seq !== lastWeatherSeq) return;
            var cur = data && data.current;
            if (!cur) { weatherUnavailable(); return; }
            var temp     = cur.temperature_2m;
            var humidity = cur.relative_humidity_2m;
            var code     = cur.weathercode;
            var desc     = WMO_CODES[code] || "Weather data received";
            setWeatherUI(temp, desc, humidity, displayName);
          });
      })
      .catch(function () {
        if (seq !== lastWeatherSeq) return;
        weatherUnavailable("Could not fetch weather");
      });
  }

  function loadWeather() {
    var locationEl = $("dash-location");
    var location = locationEl ? locationEl.value : "";
    if (!location) {
      weatherUnavailable("Select a location to see weather");
      return;
    }

    var seq = ++lastWeatherSeq;

    /* Try the local backend first; fall back to Open-Meteo on any failure */
    if (window.CropMandiAPI && CropMandiAPI.getWeather) {
      CropMandiAPI.getWeather(location)
        .then(function (payload) {
          if (seq !== lastWeatherSeq) return;
          /* Backend says available=false or missing temp → use Open-Meteo */
          if (
            !payload ||
            payload.available === false ||
            payload.temperature_c === undefined ||
            payload.temperature_c === null
          ) {
            loadWeatherFromOpenMeteo(location, seq);
            return;
          }
          setWeatherUI(
            payload.temperature_c,
            payload.description || "Conditions available",
            payload.humidity_percent !== undefined ? payload.humidity_percent : null,
            payload.location || location
          );
        })
        .catch(function () {
          if (seq !== lastWeatherSeq) return;
          /* Backend offline — use Open-Meteo free API */
          loadWeatherFromOpenMeteo(location, seq);
        });
    } else {
      loadWeatherFromOpenMeteo(location, seq);
    }
  }

  function saveAlert() {
    var ctx = selectedContext();
    if (!ctx.crop || !ctx.variety || !ctx.location) {
      setActionFeedback("Select crop, variety, and location before setting an alert.", true);
      return;
    }
    var price = currentPriceText();
    var predicted = predictedPriceText();
    if (!price || price === "—" || price === "…" || price === "Data unavailable") {
      setActionFeedback("No current price available to set an alert.", true);
      return;
    }
    var alerts = readList(ALERTS_KEY);
    var item = {
      id: Date.now(),
      createdAt: new Date().toISOString(),
      crop: ctx.crop,
      cropLabel: ctx.cropLabel,
      variety: ctx.variety,
      location: ctx.location,
      currentPrice: price,
      predictedPrice: predicted,
    };
    alerts.unshift(item);
    writeList(ALERTS_KEY, alerts);
    setActionFeedback("Alert saved for " + ctx.cropLabel + " in " + ctx.location + ".");
  }

  function savePrediction() {
    var ctx = selectedContext();
    var estimate = global.CropMandiLastEstimate;
    if (!ctx.crop || !ctx.variety || !ctx.location) {
      setActionFeedback("Select crop, variety, and location before saving.", true);
      return;
    }
    if (!estimate || estimate.unavailable) {
      setActionFeedback("No prediction available to save.", true);
      return;
    }
    var saved = readList(PREDICTIONS_KEY);
    var item = {
      id: Date.now(),
      createdAt: new Date().toISOString(),
      crop: ctx.crop,
      cropLabel: ctx.cropLabel,
      variety: ctx.variety,
      location: ctx.location,
      currentPrice: estimate.latest_observed_price,
      predictedPrice: estimate.next_session_estimate,
      latestObservationDate: estimate.latest_observation_date || null,
      unit: estimate.unit || null,
    };
    saved.unshift(item);
    writeList(PREDICTIONS_KEY, saved);
    setActionFeedback("Prediction saved for " + ctx.variety + " in " + ctx.location + ".");
  }

  function init() {
    applyGreeting();
    var locationSelect = $("dash-location");
    if (locationSelect) {
      locationSelect.addEventListener("change", loadWeather);
      if (window.MutationObserver) {
        new MutationObserver(loadWeather).observe(locationSelect, {
          childList: true,
          attributes: true,
        });
      }
    }
    var refreshButton = $("dash-refresh");
    if (refreshButton) {
      refreshButton.addEventListener("click", loadWeather);
    }
    var alertBtn = $("dash-set-alert");
    if (alertBtn) {
      alertBtn.addEventListener("click", function (event) {
        event.preventDefault();
        saveAlert();
      });
    }
    var saveBtn = $("dash-save-prediction");
    if (saveBtn) {
      saveBtn.addEventListener("click", function (event) {
        event.preventDefault();
        savePrediction();
      });
    }
    loadWeather();
  }

  global.CropMandiDashboardUI = {
    applyGreeting: applyGreeting,
    loadWeather: loadWeather,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
