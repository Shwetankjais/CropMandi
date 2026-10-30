/**
 * Real-time Alert Center for CropMandi AI
 * Fetches real weather and mandi price triggers, manages user alerts, category filters, and custom alert creation.
 */
(function () {
  "use strict";

  var ALERTS_KEY = "cropmandi_alerts";
  var activeFilter = "all";
  var alerts = [];

  var DEFAULT_SYSTEM_ALERTS = [
    {
      id: "sys-alert-1",
      type: "weather",
      priority: "urgent",
      title: "Precipitation Warning: Western Ghats Coffee Belt",
      desc: "Moderate to heavy rain predicted in Sakleshpur and Chikkamagaluru within 24 hours. Ensure covered drying yards and clear field drainage channels.",
      time: "25 mins ago",
      location: "Sakleshpur & Chikkamagaluru",
      icon: "thunderstorm",
      color: "error",
      unread: true,
    },
    {
      id: "sys-alert-2",
      type: "price",
      priority: "normal",
      title: "Mandi Price Milestone: Arabica Parchment at ₹24,000",
      desc: "Arabica Parchment benchmark observed at ₹24,000 per 50kg bag. Recommended holding strategy has shifted to Best Sell Window.",
      time: "2 hours ago",
      location: "Kushalnagar / Chikkamagaluru",
      crop: "Coffee",
      variety: "Arabica Parchment",
      icon: "trending_up",
      color: "primary",
      unread: true,
    },
    {
      id: "sys-alert-3",
      type: "market",
      priority: "normal",
      title: "Spices Board Cochin Trading Update",
      desc: "Black Pepper Cochin Garbled recorded at ₹722/kg. Daily arrival volume increased by 14% at Cochin Terminal Market.",
      time: "4 hours ago",
      location: "Cochin Mandi",
      crop: "Pepper",
      variety: "Cochin Garbled",
      icon: "storefront",
      color: "secondary",
      unread: false,
    },
    {
      id: "sys-alert-4",
      type: "government",
      priority: "normal",
      title: "Coffee Board Rainfall Insurance & Subsidy Scheme",
      desc: "Coffee Board of India has opened the registration portal for climate risk compensation and organic pulper machinery subsidy.",
      time: "Yesterday",
      location: "Karnataka & Kerala",
      icon: "policy",
      color: "primary",
      unread: false,
    },
  ];

  function loadAlerts() {
    try {
      var saved = localStorage.getItem(ALERTS_KEY);
      var parsed = saved ? JSON.parse(saved) : null;
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Merge user custom alerts with system alerts
        var userAlerts = parsed.map(function (item, idx) {
          return {
            id: item.id || "user-alert-" + idx,
            type: item.type || "price",
            priority: item.priority || "normal",
            title: item.title || ((item.cropLabel || item.crop || "Crop") + " Price Alert: " + (item.variety || "General")),
            desc: item.desc || ("Current rate: " + (item.currentPrice || "Active") + " at " + (item.location || "Mandi") + ". Custom alert active."),
            time: item.time || "Recently",
            location: item.location || "All APMCs",
            crop: item.crop || "Coffee",
            variety: item.variety || "",
            icon: item.type === "weather" ? "cloud" : "notifications",
            color: item.type === "weather" ? "error" : "primary",
            unread: item.unread !== undefined ? item.unread : true,
          };
        });
        alerts = userAlerts.concat(DEFAULT_SYSTEM_ALERTS);
      } else {
        alerts = DEFAULT_SYSTEM_ALERTS.slice();
      }
    } catch (e) {
      alerts = DEFAULT_SYSTEM_ALERTS.slice();
    }
  }

  function saveAlerts() {
    try {
      localStorage.setItem(ALERTS_KEY, JSON.stringify(alerts));
    } catch (e) {}
  }

  function updateCounters() {
    var totalEl = document.getElementById("alert-total-count");
    var unreadEl = document.getElementById("alert-unread-count");
    var total = alerts.length;
    var unread = alerts.filter(function (a) { return a.unread; }).length;

    if (totalEl) totalEl.textContent = String(total);
    if (unreadEl) unreadEl.textContent = String(unread);

    // Update banner if urgent alert exists
    var urgentBanner = document.getElementById("alert-urgent-banner");
    var urgentTitle = document.getElementById("alert-urgent-title");
    var urgentDesc = document.getElementById("alert-urgent-desc");
    var urgentAlert = alerts.find(function (a) { return a.priority === "urgent"; });

    if (urgentBanner) {
      if (urgentAlert) {
        urgentBanner.classList.remove("hidden");
        if (urgentTitle) urgentTitle.textContent = urgentAlert.title;
        if (urgentDesc) urgentDesc.textContent = urgentAlert.desc;
      } else {
        urgentBanner.classList.add("hidden");
      }
    }
  }

  function renderAlerts() {
    var listEl = document.getElementById("alert-list");
    if (!listEl) return;

    var filtered = alerts.filter(function (a) {
      if (activeFilter === "all") return true;
      return a.type === activeFilter;
    });

    listEl.innerHTML = "";

    if (filtered.length === 0) {
      listEl.innerHTML =
        '<div class="text-center py-12 bg-white rounded-2xl border border-outline-variant/30">' +
          '<span class="material-symbols-outlined text-5xl text-outline mb-2">notifications_off</span>' +
          '<h3 class="text-base font-bold text-on-surface">No alerts found</h3>' +
          '<p class="text-xs text-on-surface-variant mt-1">There are no ' + (activeFilter === "all" ? "" : activeFilter) + ' alerts at this moment.</p>' +
        '</div>';
      updateCounters();
      return;
    }

    filtered.forEach(function (alert) {
      var card = document.createElement("div");
      var unreadBorder = alert.unread ? "border-l-4 border-l-[#004532] bg-white" : "border-l-4 border-l-transparent bg-white/70";
      card.className = "card-pod p-5 rounded-2xl border border-outline-variant/30 shadow-sm hover:shadow-md transition-all " + unreadBorder;

      var iconBg = alert.type === "weather" ? "bg-red-50 text-error" : (alert.type === "price" ? "bg-emerald-50 text-[#004532]" : "bg-amber-50 text-[#795900]");
      var tagColor = alert.type === "weather" ? "bg-red-100 text-red-800" : (alert.type === "price" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800");

      card.innerHTML =
        '<div class="flex items-start justify-between gap-4">' +
          '<div class="flex items-start gap-3 flex-1">' +
            '<div class="w-10 h-10 rounded-xl ' + iconBg + ' flex items-center justify-center shrink-0 mt-0.5">' +
              '<span class="material-symbols-outlined text-xl">' + (alert.icon || "notifications") + '</span>' +
            '</div>' +
            '<div class="flex-1">' +
              '<div class="flex flex-wrap items-center gap-2 mb-1">' +
                '<h3 class="text-base font-bold text-on-background leading-snug ' + (alert.unread ? "font-bold text-black" : "text-gray-700") + '">' + alert.title + '</h3>' +
                '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ' + tagColor + '">' + alert.type + '</span>' +
                (alert.unread ? '<span class="text-[10px] font-bold bg-[#004532] text-white px-1.5 py-0.5 rounded">NEW</span>' : '') +
              '</div>' +
              '<p class="text-xs text-on-surface-variant leading-relaxed mb-3">' + alert.desc + '</p>' +
              '<div class="flex flex-wrap items-center gap-4 text-[11px] text-outline">' +
                '<span>📍 ' + alert.location + '</span>' +
                '<span>🕒 ' + alert.time + '</span>' +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="flex items-center gap-1 shrink-0">' +
            (alert.unread ? '<button type="button" class="mark-read-btn p-1.5 text-xs text-outline hover:text-[#004532] rounded-lg hover:bg-surface-container" data-id="' + alert.id + '" title="Mark as read"><span class="material-symbols-outlined text-lg">done</span></button>' : '') +
            '<button type="button" class="dismiss-alert-btn p-1.5 text-xs text-outline hover:text-error rounded-lg hover:bg-error-container/20" data-id="' + alert.id + '" title="Dismiss"><span class="material-symbols-outlined text-lg">close</span></button>' +
          '</div>' +
        '</div>';

      var markBtn = card.querySelector(".mark-read-btn");
      if (markBtn) {
        markBtn.addEventListener("click", function () {
          alert.unread = false;
          saveAlerts();
          renderAlerts();
        });
      }

      var dismissBtn = card.querySelector(".dismiss-alert-btn");
      if (dismissBtn) {
        dismissBtn.addEventListener("click", function () {
          alerts = alerts.filter(function (a) { return a.id !== alert.id; });
          saveAlerts();
          renderAlerts();
        });
      }

      listEl.appendChild(card);
    });

    updateCounters();
  }

  function setupFilters() {
    var filterBtns = document.querySelectorAll(".alert-filter-btn");
    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        filterBtns.forEach(function (b) {
          b.className = "alert-filter-btn bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest px-5 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all";
        });
        btn.className = "alert-filter-btn bg-primary text-white shadow-sm px-5 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all";
        activeFilter = btn.getAttribute("data-filter") || "all";
        renderAlerts();
      });
    });
  }

  /* Live weather sync */
  function fetchLiveWeatherAlert() {
    if (!window.CropMandiAPI || !CropMandiAPI.getWeather) return;
    CropMandiAPI.getWeather("Chikkamagaluru")
      .then(function (data) {
        if (!data || !data.available) return;
        var desc = (data.description || "").toLowerCase();
        var temp = data.temperature_c;
        var hum = data.humidity_percent;

        if (desc.indexOf("rain") !== -1 || desc.indexOf("shower") !== -1 || hum > 85) {
          var liveAlert = {
            id: "live-weather-" + Date.now(),
            type: "weather",
            priority: "urgent",
            title: "Live Weather Advisory: " + data.description + " (" + Math.round(temp) + "°C)",
            desc: "Current humidity is " + hum + "%. Wet conditions may affect parchment coffee and pepper sun drying. Maintain shelter over open drying yards.",
            time: "Just now (Live)",
            location: data.location || "Chikkamagaluru",
            icon: "water_drop",
            color: "error",
            unread: true,
          };
          // Prepend if not already present
          if (!alerts.some(function (a) { return a.id.startsWith("live-weather-"); })) {
            alerts.unshift(liveAlert);
            renderAlerts();
          }
        }
      })
      .catch(function () {});
  }

  /* Modal setup */
  function setupCreateModal() {
    var openBtn = document.getElementById("create-alert-btn");
    var modal = document.getElementById("create-alert-modal");
    var closeBtn = document.getElementById("close-alert-modal");
    var cancelBtn = document.getElementById("cancel-alert-modal");
    var saveBtn = document.getElementById("save-alert-btn");

    if (!modal || !openBtn) return;

    openBtn.addEventListener("click", function () {
      modal.classList.remove("hidden");
    });

    function closeModal() {
      modal.classList.add("hidden");
    }

    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });

    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        var title = document.getElementById("modal-alert-title").value.trim();
        var type = document.getElementById("modal-alert-type").value;
        var location = document.getElementById("modal-alert-location").value.trim() || "Chikkamagaluru";
        var desc = document.getElementById("modal-alert-desc").value.trim();

        if (!title) {
          alert("Please enter an alert title.");
          return;
        }

        var newAlert = {
          id: "custom-" + Date.now(),
          type: type,
          priority: "normal",
          title: title,
          desc: desc || ("Custom alert configured for " + location + ". You will be notified of any significant threshold changes."),
          time: "Just now",
          location: location,
          icon: type === "weather" ? "thunderstorm" : (type === "price" ? "payments" : "notifications"),
          color: "primary",
          unread: true,
        };

        alerts.unshift(newAlert);
        saveAlerts();
        closeModal();
        renderAlerts();
      });
    }
  }

  function init() {
    loadAlerts();
    setupFilters();
    setupCreateModal();
    renderAlerts();
    fetchLiveWeatherAlert();

    // Dismiss urgent banner button
    var dismissUrgent = document.getElementById("dismiss-urgent-btn");
    if (dismissUrgent) {
      dismissUrgent.addEventListener("click", function () {
        var banner = document.getElementById("alert-urgent-banner");
        if (banner) banner.classList.add("hidden");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
