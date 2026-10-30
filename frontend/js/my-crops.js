/**
 * My Crops - CropMandi AI
 * Inventory cards are independent of Dashboard dropdowns.
 * Prices are fetched per saved crop (commodity + variety + location).
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
  var STORAGE_KEY = "cropmandi_my_crops";
  var COFFEE_IMAGE =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuBy6kQmho-Q4IX8qPbB4k20K0YhwM6_YjAasuegM-mNNcnag1qFmo5To8wsFkIcHky_jgunjuHmkrBASCC9kQWgCAgfohgeV2a4AySRIWom7CBoPQPPOXZqdbgc14xBDYnE5RWoqt333VDrUvdadpwN7f1xe9QhXwsUuhNsr0JsWR23Qw0Tr4jOYRM4Wom-ad3iHWgUq3ph4QfW1q3epW1D-LXPbgv_XTcKAu09hd9TOWkIwkp_0Uv-";
  var PEPPER_IMAGE =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuBa6CUAA7uQRUK0gLXGEunIHEQrBZxydHO4IM6ix_mnfNiFkttcq0EYyT_CMVtYIOH_TAs5ZSlDSytimYLy9z-pKx_0-X4isJPVDq4HAEs7EV5j0J5RTx18AzKOHIcx2kuIL1VHtbxDQO80tWwbwLO61RqomyHhoLJpwLqjMf2kSqH5imMm7wnyPQcUDiuj69a2KTRunqS3i9O3lRoZq1Otvs8RZ1BbAFEf81erOxXV1tL2nNoO2p1s";

  var cropGallery;
  var totalCropsEl;
  var totalQuantityEl;
  var addCropButton;
  var modal;
  var modalCropSelect;
  var modalVarietySelect;
  var modalQuantityInput;
  var modalLocationSelect;
  var modalLocationLoading;
  var modalLocationError;
  var modalCancelButton;
  var modalSaveButton;
  var modalCloseButton;

  var deleteModal;
  var deleteModalMessage;
  var deleteCancelButton;
  var deleteConfirmButton;
  var cropToDeleteId = null;

  var userCrops = [];

  function $(id) {
    return document.getElementById(id);
  }

  function seriesForCommodity(code) {
    return code === "pepper" ? PEPPER_SERIES : COFFEE_SERIES;
  }

  function commodityLabel(code) {
    return code === "pepper" ? "Black Pepper" : "Coffee";
  }

  function normalizeTypeKey(value) {
    return String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toUpperCase();
  }

  function numericPrice(value) {
    var n = typeof value === "number" ? value : Number(value);
    return Number.isFinite(n) && n > 0 ? n : NaN;
  }

  function formatPrice(price) {
    if (!Number.isFinite(price) || price <= 0) {
      return "Price unavailable";
    }
    return "₹" + Number(price).toLocaleString("en-IN");
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

  function observationsForCrop(crop, pricesPayload) {
    var observations = (pricesPayload && pricesPayload.observations) || [];
    var selectedKey = normalizeTypeKey(crop.variety);
    if (crop.commodity === "coffee") {
      if (!selectedKey) {
        return observations;
      }
      return observations.filter(function (obs) {
        return normalizeTypeKey(obs.type) === selectedKey;
      });
    }
    if (crop.commodity !== "pepper") {
      return [];
    }
    var matched = observations.filter(function (obs) {
      return pepperMatchesSelection(selectedKey, obs);
    });
    if (matched.length) {
      return matched;
    }
    if (!selectedKey || selectedKey.indexOf("GARB") !== -1 || selectedKey === "WHITE") {
      return observations;
    }
    return matched;
  }

  var FALLBACK_LOCATIONS = {
    coffee: ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan", "Kushalnagar", "Somwarpet", "Gonikoppal"],
    pepper: ["Kochi (Cochin)", "Sirsi", "Wayanad", "Idukki", "Shivamogga", "Madikeri", "Chikkamagaluru"]
  };

  function loadLocationsForCommodity(commodity) {
    var fallback = FALLBACK_LOCATIONS[commodity] || [];
    if (!window.CropMandiAPI || !CropMandiAPI.getMarkets) {
      return Promise.resolve(fallback);
    }

    if (modalLocationLoading) {
      modalLocationLoading.classList.remove("hidden");
    }
    if (modalLocationError) {
      modalLocationError.classList.add("hidden");
    }

    return CropMandiAPI.getMarkets(commodity)
      .then(function (payload) {
        if (modalLocationLoading) {
          modalLocationLoading.classList.add("hidden");
        }
        var names = ((payload && payload.locations) || [])
          .map(function (row) {
            return row && row.name;
          })
          .filter(Boolean);
        return names.length ? names : fallback;
      })
      .catch(function () {
        if (modalLocationLoading) {
          modalLocationLoading.classList.add("hidden");
        }
        return fallback;
      });
  }

  function loadUserCrops() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      var parsed = stored ? JSON.parse(stored) : [];
      if (Array.isArray(parsed) && parsed.length > 0) {
        userCrops = parsed.filter(function (crop) {
          return crop && (crop.commodity === "coffee" || crop.commodity === "pepper");
        });
      }
      if (!userCrops || userCrops.length === 0) {
        userCrops = [
          {
            id: "crop-seed-1",
            commodity: "coffee",
            variety: "Arabica Parchment",
            quantity: 45,
            location: "Chikkamagaluru",
            addedAt: new Date().toISOString()
          },
          {
            id: "crop-seed-2",
            commodity: "pepper",
            variety: "Cochin Garbled",
            quantity: 20,
            location: "Madikeri",
            addedAt: new Date().toISOString()
          },
          {
            id: "crop-seed-3",
            commodity: "coffee",
            variety: "Robusta Cherry",
            quantity: 35,
            location: "Sakleshpur",
            addedAt: new Date().toISOString()
          }
        ];
        saveUserCrops();
      }
    } catch (e) {
      console.error("Failed to load user crops:", e);
      userCrops = [];
    }
  }

  function saveUserCrops() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(userCrops));
    } catch (e) {
      console.error("Failed to save user crops:", e);
    }
  }

  function updateSummary() {
    var totalCrops = userCrops.length;
    var totalQuantity = userCrops.reduce(function (sum, crop) {
      return sum + (Number(crop.quantity) || 0);
    }, 0);

    if (totalCropsEl) {
      totalCropsEl.innerHTML = totalCrops + ' <span class="text-body-md font-body-md text-on-surface-variant font-normal">' + (totalCrops === 1 ? "crop" : "crops") + '</span>';
    }
    if (totalQuantityEl) {
      totalQuantityEl.innerHTML = totalQuantity + ' <span class="text-body-md font-body-md text-on-surface-variant font-normal">qtl</span>';
    }
  }

  function fetchCropPrice(crop, priceEl) {
    if (!priceEl) {
      return;
    }
    if (!crop.commodity || !crop.variety) {
      priceEl.textContent = "Price unavailable";
      return;
    }
    if (!window.CropMandiAPI) {
      priceEl.textContent = "₹" + (crop.commodity === "coffee" ? "24,000" : "722");
      return;
    }

    CropMandiAPI.getMarketPrices(crop.commodity, crop.location || "Sakleshpur")
      .then(function (payload) {
        var rows = observationsForCrop(crop, payload);
        var price = NaN;
        var i;
        for (i = 0; i < rows.length; i += 1) {
          price = numericPrice(rows[i] && rows[i].price);
          if (Number.isFinite(price)) {
            break;
          }
        }
        if (Number.isFinite(price)) {
          priceEl.textContent = formatPrice(price);
          return;
        }
        // Fallback to latest prices
        return CropMandiAPI.getLatestPrices(crop.commodity).then(function (latPayload) {
          var obs = (latPayload && latPayload.observations) || [];
          var match = obs.find(function (o) {
            return normalizeTypeKey(o.series) === normalizeTypeKey(crop.variety);
          });
          if (match && Number.isFinite(match.price)) {
            priceEl.textContent = formatPrice(match.price);
          } else {
            priceEl.textContent = crop.commodity === "coffee" ? "₹24,000 / 50kg" : "₹722 / kg";
          }
        });
      })
      .catch(function () {
        priceEl.textContent = crop.commodity === "coffee" ? "₹24,000 / 50kg" : "₹722 / kg";
      });
  }

  function createCropCard(crop) {
    var card = document.createElement("div");
    card.className =
      "bg-surface-container-lowest rounded-xl card-shadow border-t border-white/50 p-6 flex flex-col group card-hover transition-all duration-300 relative";

    var commodityName = commodityLabel(crop.commodity);
    var cropLocation = crop.location || "Unknown";
    var imageUrl = crop.commodity === "pepper" ? PEPPER_IMAGE : COFFEE_IMAGE;
    var imageAlt = commodityName;
    var priceId = "crop-price-" + crop.id;

    card.innerHTML =
      '<div class="h-48 mb-6 flex items-center justify-center bg-surface-container-low rounded-lg p-4 relative">' +
        '<img alt="' + imageAlt + '" class="w-full h-full object-contain drop-shadow-xl transform group-hover:scale-105 transition-transform duration-500" src="' + imageUrl + '"/>' +
      "</div>" +
      '<div class="flex justify-between items-start mb-4">' +
        "<div>" +
          '<h3 class="text-headline-md font-headline-md text-on-background mb-1">' + commodityName + "</h3>" +
          '<span class="inline-block px-2 py-1 bg-surface-container text-on-surface-variant rounded text-label-sm font-label-sm font-medium">' + crop.variety + "</span>" +
        "</div>" +
      "</div>" +
      '<div class="grid grid-cols-2 gap-y-4 gap-x-2 mb-6">' +
        "<div>" +
          '<p class="text-label-sm font-label-sm text-outline mb-1">QUANTITY</p>' +
          '<p class="text-data-tabular font-data-tabular text-on-background">' + crop.quantity + " qtl</p>" +
        "</div>" +
        "<div>" +
          '<p class="text-label-sm font-label-sm text-outline mb-1">LOCATION</p>' +
          '<p class="text-data-tabular font-data-tabular text-on-background truncate">' + cropLocation + "</p>" +
        "</div>" +
        "<div>" +
          '<p class="text-label-sm font-label-sm text-outline mb-1">PRICE</p>' +
          '<p class="text-data-tabular font-data-tabular text-on-background" id="' + priceId + '">…</p>' +
        "</div>" +
      "</div>" +
      '<div class="mt-auto pt-4 border-t border-outline-variant/30 flex items-center gap-2">' +
        '<a href="../cropmandi_ai_dashboard/code.html" class="flex-1 py-2 px-3 rounded-lg text-xs font-bold bg-primary text-white hover:bg-primary-light transition-all flex items-center justify-center gap-1.5 shadow-sm view-dash-btn" data-crop="' + crop.commodity + '" data-variety="' + crop.variety + '" data-location="' + cropLocation + '">' +
          '<span class="material-symbols-outlined text-sm">dashboard</span> Track Market' +
        '</a>' +
        '<button class="py-2 px-3 rounded-lg text-xs font-bold text-error border border-error/30 hover:bg-error-container hover:text-on-error-container transition-colors delete-crop-btn" data-id="' + crop.id + '" title="Delete crop">' +
          '<span class="material-symbols-outlined text-sm">delete</span>' +
        '</button>' +
      "</div>";

    var viewDashBtn = card.querySelector(".view-dash-btn");
    if (viewDashBtn) {
      viewDashBtn.addEventListener("click", function () {
        localStorage.setItem("cropmandi_dash_commodity", crop.commodity);
        localStorage.setItem("cropmandi_dash_variety", crop.variety);
        localStorage.setItem("cropmandi_dash_location", cropLocation);
      });
    }

    var deleteBtn = card.querySelector(".delete-crop-btn");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function (event) {
        event.preventDefault();
        deleteCrop(crop.id);
      });
    }

    fetchCropPrice(crop, card.querySelector("#" + priceId));
    return card;
  }

  function renderCrops() {
    if (!cropGallery) {
      return;
    }

    cropGallery.innerHTML = "";

    if (userCrops.length === 0) {
      var emptyState = document.createElement("div");
      emptyState.className = "col-span-1 md:col-span-2 lg:col-span-3 text-center py-12";
      emptyState.innerHTML =
        '<div class="flex flex-col items-center gap-4">' +
          '<span class="material-symbols-outlined text-[64px] text-outline opacity-30">agriculture</span>' +
          '<p class="text-body-lg font-body-lg text-on-surface-variant">No crops added yet</p>' +
          '<p class="text-body-md font-body-md text-on-surface-variant">Click "Add New Crop" to get started</p>' +
        "</div>";
      cropGallery.appendChild(emptyState);
      updateSummary();
      return;
    }

    userCrops.forEach(function (crop) {
      cropGallery.appendChild(createCropCard(crop));
    });
    updateSummary();
  }

  function deleteCrop(cropId) {
    var cropToDelete = userCrops.find(function (crop) {
      return crop.id === cropId;
    });

    if (!cropToDelete) {
      return;
    }

    cropToDeleteId = cropId;
    var message =
      "Are you sure you want to remove " +
      commodityLabel(cropToDelete.commodity) +
      " (" +
      cropToDelete.variety +
      ") from your inventory?";

    if (deleteModalMessage) {
      deleteModalMessage.textContent = message;
    }

    if (deleteModal) {
      deleteModal.classList.remove("hidden");
    }
  }

  function confirmDeleteCrop() {
    if (!cropToDeleteId) {
      return;
    }

    userCrops = userCrops.filter(function (crop) {
      return crop.id !== cropToDeleteId;
    });
    saveUserCrops();
    cropToDeleteId = null;
    closeDeleteModal();
    renderCrops();
  }

  function closeDeleteModal() {
    if (deleteModal) {
      deleteModal.classList.add("hidden");
    }
    cropToDeleteId = null;
  }

  function resetModalLocation() {
    if (!modalLocationSelect) {
      return;
    }
    modalLocationSelect.innerHTML = "";
    var defaultLocOption = document.createElement("option");
    defaultLocOption.value = "";
    defaultLocOption.textContent = "Select location...";
    modalLocationSelect.appendChild(defaultLocOption);
  }

  function openModal() {
    if (!modal) {
      return;
    }

    if (modalCropSelect) {
      modalCropSelect.value = "";
    }
    if (modalVarietySelect) {
      modalVarietySelect.innerHTML = "";
      var defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = "Select variety...";
      modalVarietySelect.appendChild(defaultOption);
    }
    if (modalQuantityInput) {
      modalQuantityInput.value = "";
    }
    resetModalLocation();
    if (modalLocationLoading) {
      modalLocationLoading.classList.add("hidden");
    }
    if (modalLocationError) {
      modalLocationError.classList.add("hidden");
    }

    modal.classList.remove("hidden");
  }

  function closeModal() {
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
  }

  function fillVarietyOptions(commodity) {
    if (!modalVarietySelect) {
      return;
    }

    var series = seriesForCommodity(commodity);
    modalVarietySelect.innerHTML = "";

    var defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select variety...";
    modalVarietySelect.appendChild(defaultOption);

    series.forEach(function (name) {
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      modalVarietySelect.appendChild(opt);
    });
  }

  function fillLocationOptions(locations) {
    if (!modalLocationSelect) {
      return;
    }

    modalLocationSelect.innerHTML = "";

    var defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select location...";
    modalLocationSelect.appendChild(defaultOption);

    locations.forEach(function (name) {
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      modalLocationSelect.appendChild(opt);
    });
  }

  function saveCrop() {
    var commodity = modalCropSelect ? modalCropSelect.value : "";
    var variety = modalVarietySelect ? modalVarietySelect.value : "";
    var quantity = modalQuantityInput ? Number(modalQuantityInput.value) : 0;
    var location = modalLocationSelect ? modalLocationSelect.value : "";

    if (commodity !== "coffee" && commodity !== "pepper") {
      alert("Please select a commodity.");
      return;
    }
    if (!variety) {
      alert("Please select a variety.");
      return;
    }
    if (!quantity || quantity <= 0) {
      alert("Please enter a valid quantity greater than 0.");
      return;
    }
    if (!location) {
      alert("Please select a location.");
      return;
    }

    userCrops.push({
      id: Date.now().toString(),
      commodity: commodity,
      variety: variety,
      quantity: quantity,
      location: location,
      addedAt: new Date().toISOString(),
    });

    saveUserCrops();
    closeModal();
    renderCrops();
  }

  function init() {
    cropGallery = $("crop-gallery");
    totalCropsEl = $("total-crops");
    totalQuantityEl = $("total-quantity");
    addCropButton = $("add-crop-button");
    modal = $("add-crop-modal");
    modalCropSelect = $("modal-crop-select");
    modalVarietySelect = $("modal-variety-select");
    modalQuantityInput = $("modal-quantity-input");
    modalLocationSelect = $("modal-location-select");
    modalLocationLoading = $("modal-location-loading");
    modalLocationError = $("modal-location-error");
    modalCancelButton = $("modal-cancel-button");
    modalSaveButton = $("modal-save-button");
    modalCloseButton = $("modal-close-button");

    deleteModal = $("delete-modal");
    deleteModalMessage = $("delete-modal-message");
    deleteCancelButton = $("delete-cancel-button");
    deleteConfirmButton = $("delete-confirm-button");

    if (!cropGallery || !addCropButton) {
      return;
    }

    loadUserCrops();
    renderCrops();

    addCropButton.addEventListener("click", openModal);

    if (modalCropSelect) {
      modalCropSelect.addEventListener("change", function () {
        fillVarietyOptions(modalCropSelect.value);
        resetModalLocation();
        if (modalCropSelect.value === "coffee" || modalCropSelect.value === "pepper") {
          loadLocationsForCommodity(modalCropSelect.value).then(function (locations) {
            if (locations && locations.length > 0) {
              fillLocationOptions(locations);
            }
          });
        }
      });
    }

    if (modalCancelButton) {
      modalCancelButton.addEventListener("click", closeModal);
    }
    if (modalCloseButton) {
      modalCloseButton.addEventListener("click", closeModal);
    }
    if (modalSaveButton) {
      modalSaveButton.addEventListener("click", saveCrop);
    }
    if (deleteCancelButton) {
      deleteCancelButton.addEventListener("click", closeDeleteModal);
    }
    if (deleteConfirmButton) {
      deleteConfirmButton.addEventListener("click", confirmDeleteCrop);
    }
    if (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) {
          closeModal();
        }
      });
    }
    if (deleteModal) {
      deleteModal.addEventListener("click", function (event) {
        if (event.target === deleteModal) {
          closeDeleteModal();
        }
      });
    }
    if (modalVarietySelect) {
      modalVarietySelect.innerHTML = "";
      var defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = "Select variety...";
      modalVarietySelect.appendChild(defaultOption);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
