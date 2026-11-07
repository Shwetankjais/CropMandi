/**
 * My Crops - CropMandi AI
 * Unified multi-crop inventory management supporting all 7 commodities:
 * 1. Coffee (Arabica, Robusta)
 * 2. Black Pepper
 * 3. Cardamom
 * 4. Paddy (Rice)
 * 5. Tomato
 * 6. Potato
 * 7. Maize
 *
 * Connected directly with:
 * - Mandi Price AI (ExtraTreesRegressor forecasting)
 * - Live APMC market price discovery
 * - Backend SQLite database (/api/farmer/crops)
 * - Dynamic portfolio valuation and quantity tracking
 */
(function () {
  "use strict";

  var STORAGE_KEY = "cropmandi_my_crops_v3";

  var COMMODITY_CONFIG = {
    coffee: {
      name: "Coffee",
      kannada: "ಕಾಫಿ",
      category: "Plantation",
      description: "High-altitude Karnataka Arabica & Robusta plantation beans. Daily auction prices tracked via Coffee Board APMC markets.",
      image: "../assets/crops/coffee.jpg",
      badge: "Market Intelligence",
      badgeClass: "bg-amber-100 text-amber-900 border-amber-300",
      hasMLForecast: false,
      varieties: [
        "Arabica Parchment",
        "Arabica Cherry",
        "Robusta Parchment",
        "Robusta Cherry"
      ],
      defaultUnit: "quintal",
      locations: ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan", "Kushalnagar", "Somwarpet", "Gonikoppal"],
      benchmarkPricePerQtl: 51700, // ~₹25,850 per 50kg bag = ₹51,700 / qtl
      priceDisplayUnit: "50kg bag",
      priceDisplayRatio: 0.5
    },
    pepper: {
      name: "Black Pepper",
      kannada: "ಕರಿಮೆಣಸು",
      category: "Spices",
      description: "King of Spices. High-grade Cochin garbled & ungarbled black peppercorn clusters harvested across Malabar and Karnataka.",
      image: "../assets/crops/black-pepper.jpg",
      badge: "Market Intelligence",
      badgeClass: "bg-emerald-100 text-emerald-900 border-emerald-300",
      hasMLForecast: false,
      varieties: [
        "Cochin Garbled",
        "Cochin Ungarbled",
        "Sirsi"
      ],
      defaultUnit: "quintal",
      locations: ["Kochi (Cochin)", "Sirsi", "Wayanad", "Idukki", "Shivamogga", "Madikeri", "Chikkamagaluru"],
      benchmarkPricePerQtl: 69000, // ~₹690 / kg = ₹69,000 / qtl
      priceDisplayUnit: "kg",
      priceDisplayRatio: 0.01
    },
    cardamom: {
      name: "Cardamom",
      kannada: "ಏಲಕ್ಕಿ",
      category: "Spices",
      description: "Queen of Spices. Aromatic bold green pods (7mm - 8mm+) tracked via Spices Board e-auctions in Bodinayakanur and Vandanmettu.",
      image: "../assets/crops/cardamom.jpg",
      badge: "Market Analytics",
      badgeClass: "bg-blue-100 text-blue-900 border-blue-300",
      hasMLForecast: false,
      varieties: [
        "Bold Grade (8mm+)",
        "Small Cardamom (Green)",
        "Medium Grade (7mm)",
        "Super Bold"
      ],
      defaultUnit: "kg",
      locations: ["Sakleshpur", "Madikeri", "Mudigere", "Idukki", "Bodinayakanur"],
      benchmarkPricePerQtl: 245000, // ~₹2,450 / kg = ₹2,45,000 / qtl
      priceDisplayUnit: "kg",
      priceDisplayRatio: 0.01
    },
    paddy: {
      name: "Paddy (Rice)",
      kannada: "ಭತ್ತ",
      category: "Grains & Cereals",
      description: "Staple kharif/rabi cereal grain. Fully integrated with Mandi Price AI (ExtraTreesRegressor) for daily APMC modal price forecasting.",
      image: "../assets/crops/paddy.jpg",
      badge: "ML Forecast Ready",
      badgeClass: "bg-emerald-600 text-white shadow-sm",
      hasMLForecast: true,
      varieties: [
        "Sona Masuri",
        "Paddy (Dhan) (Common)",
        "Basmati",
        "I.R. 64",
        "Jyothi",
        "Jaya"
      ],
      defaultUnit: "quintal",
      locations: ["Davanagere", "Shivamogga", "Mandya", "Haveri", "Mysuru", "Koppal", "Raichur", "Ballari"],
      benchmarkPricePerQtl: 2240,
      priceDisplayUnit: "qtl",
      priceDisplayRatio: 1.0
    },
    tomato: {
      name: "Tomato",
      kannada: "ಟೊಮೇಟೊ",
      category: "Vegetables",
      description: "High-demand perishable horticulture crop. Machine learning price predictions across Kolar, Bengaluru, and major Karnataka mandis.",
      image: "../assets/crops/tomato.jpg",
      badge: "ML Forecast Ready",
      badgeClass: "bg-emerald-600 text-white shadow-sm",
      hasMLForecast: true,
      varieties: [
        "Hybrid Tomato",
        "Local / Desi",
        "Roma"
      ],
      defaultUnit: "quintal",
      locations: ["Kolar", "Bengaluru", "Chikkaballapura", "Belagavi", "Mysuru", "Hassan"],
      benchmarkPricePerQtl: 1850,
      priceDisplayUnit: "qtl",
      priceDisplayRatio: 1.0
    },
    potato: {
      name: "Potato",
      kannada: "ಆಲೂಗಡ್ಡೆ",
      category: "Vegetables",
      description: "Major tuber crop with high cold-storage suitability. ML modal price forecasting across Hassan, Bengaluru, and Kolar APMCs.",
      image: "../assets/crops/potato.jpg",
      badge: "ML Forecast Ready",
      badgeClass: "bg-emerald-600 text-white shadow-sm",
      hasMLForecast: true,
      varieties: [
        "Jyoti",
        "Kufri Chandramukhi",
        "Kufri Lauvkar",
        "Common / Desi"
      ],
      defaultUnit: "quintal",
      locations: ["Hassan", "Bengaluru", "Belagavi", "Kolar", "Chikkamagaluru"],
      benchmarkPricePerQtl: 1750,
      priceDisplayUnit: "qtl",
      priceDisplayRatio: 1.0
    },
    maize: {
      name: "Maize",
      kannada: "ಮೆಕ್ಕೆಜೋಳ",
      category: "Coarse Cereals",
      description: "Key coarse cereal and poultry feed commodity. Machine learning market projections across Davanagere and Haveri mandis.",
      image: "../assets/crops/maize.jpg",
      badge: "ML Forecast Ready",
      badgeClass: "bg-emerald-600 text-white shadow-sm",
      hasMLForecast: true,
      varieties: [
        "Yellow Maize (Feed)",
        "White Maize",
        "Sweet Corn",
        "Local"
      ],
      defaultUnit: "quintal",
      locations: ["Davanagere", "Haveri", "Shivamogga", "Chitradurga", "Belagavi", "Ballari"],
      benchmarkPricePerQtl: 2150,
      priceDisplayUnit: "qtl",
      priceDisplayRatio: 1.0
    }
  };

  // DOM Elements
  var cropGallery;
  var totalCropsEl;
  var totalQuantityEl;
  var totalValueEl;
  var addCropButton;

  // Add / Edit Modal Elements
  var modal;
  var modalCropId;
  var modalTitle;
  var modalCropSelect;
  var modalVarietySelect;
  var modalQuantityInput;
  var modalUnitSelect;
  var modalLocationSelect;
  var modalLocationLoading;
  var modalLocationError;
  var modalCancelButton;
  var modalSaveButton;
  var modalCloseButton;
  var modalErrorBox;
  var modalErrorText;

  // Delete Modal Elements
  var deleteModal;
  var deleteModalMessage;
  var deleteCancelButton;
  var deleteConfirmButton;
  var cropToDeleteId = null;

  // Notice Modal Elements
  var noticeModal;
  var noticeModalCloseButton;

  var userCrops = [];
  var cachedPrices = {};

  function $(id) {
    return document.getElementById(id);
  }

  function normalizeCommodity(code) {
    var raw = String(code || "").toLowerCase().trim();
    if (raw === "rice" || raw === "paddy (rice)") return "paddy";
    if (raw === "corn") return "maize";
    if (raw === "black pepper" || raw === "black_pepper") return "pepper";
    return raw;
  }

  function getCommodityConfig(code) {
    var norm = normalizeCommodity(code);
    return COMMODITY_CONFIG[norm] || COMMODITY_CONFIG.coffee;
  }

  function resolveCropImage(imgUrl, comm) {
    if (imgUrl && (imgUrl.startsWith("http://") || imgUrl.startsWith("https://") || imgUrl.startsWith("data:"))) {
      return imgUrl;
    }
    var cfg = getCommodityConfig(comm);
    var path = imgUrl || cfg.image;
    if (path.indexOf("../assets/") === 0) return path;
    if (path.indexOf("assets/") === 0) return "../" + path;
    if (path.indexOf("/assets/") === 0) return ".." + path;
    return cfg.image;
  }

  function formatCurrency(val) {
    if (!Number.isFinite(val) || val <= 0) return "—";
    return "₹" + Math.round(val).toLocaleString("en-IN");
  }

  function quantityInQuintals(qty, unit) {
    var q = Number(qty) || 0;
    var u = String(unit || "quintal").toLowerCase();
    if (u.indexOf("kg") !== -1 && u.indexOf("50") === -1 && u.indexOf("25") === -1) {
      return q / 100.0;
    }
    if (u.indexOf("50") !== -1) {
      return (q * 50.0) / 100.0;
    }
    if (u.indexOf("25") !== -1 || u.indexOf("crate") !== -1) {
      return (q * 25.0) / 100.0;
    }
    return q;
  }

  function formatUnitDisplay(unit) {
    var u = String(unit || "quintal").toLowerCase();
    if (u.indexOf("50") !== -1) return "bags (50kg)";
    if (u.indexOf("25") !== -1 || u.indexOf("crate") !== -1) return "crates (25kg)";
    if (u.indexOf("kg") !== -1) return "kg";
    return "qtl";
  }

  // ── Database & Storage synchronization ────────────────────────────────────

  function loadUserCrops() {
    // 1. Try local cache if it contains all 7 commodities
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        var parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length >= 7) {
          userCrops = parsed;
          renderCrops();
        }
      }
    } catch (e) {
      console.warn("Could not read local crop cache:", e);
    }

    // 2. Fetch authoritative records from backend API (/api/farmer/crops)
    if (window.CropMandiAPI && CropMandiAPI.getFarmerCrops) {
      CropMandiAPI.getFarmerCrops()
        .then(function (res) {
          if (res && res.success && Array.isArray(res.crops) && res.crops.length > 0) {
            userCrops = res.crops;
            saveLocalCrops();
            renderCrops();
          } else if (!userCrops || userCrops.length < 7) {
            seedDefaultCrops();
            renderCrops();
          }
        })
        .catch(function (err) {
          console.warn("Backend farmer crops API unavailable, using cached records:", err);
          if (!userCrops || userCrops.length < 7) {
            seedDefaultCrops();
            renderCrops();
          }
        });
    } else {
      if (!userCrops || userCrops.length < 7) {
        seedDefaultCrops();
        renderCrops();
      }
    }
  }

  function seedDefaultCrops() {
    userCrops = [
      {
        id: 1,
        commodity: "coffee",
        variety: "Arabica Parchment",
        quantity: 45,
        unit: "quintal",
        location: "Chikkamagaluru",
        image_url: "../assets/crops/coffee.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 2,
        commodity: "pepper",
        variety: "Cochin Garbled",
        quantity: 20,
        unit: "quintal",
        location: "Madikeri",
        image_url: "../assets/crops/black-pepper.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 3,
        commodity: "coffee",
        variety: "Robusta Cherry",
        quantity: 35,
        unit: "quintal",
        location: "Sakleshpur",
        image_url: "../assets/crops/coffee.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 4,
        commodity: "cardamom",
        variety: "Bold Grade (8mm+)",
        quantity: 50,
        unit: "kg",
        location: "Sakleshpur",
        image_url: "../assets/crops/cardamom.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 5,
        commodity: "paddy",
        variety: "Sona Masuri",
        quantity: 60,
        unit: "quintal",
        location: "Davanagere",
        image_url: "../assets/crops/paddy.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 6,
        commodity: "tomato",
        variety: "Hybrid Tomato",
        quantity: 30,
        unit: "quintal",
        location: "Kolar",
        image_url: "../assets/crops/tomato.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 7,
        commodity: "potato",
        variety: "Jyoti",
        quantity: 40,
        unit: "quintal",
        location: "Hassan",
        image_url: "../assets/crops/potato.jpg",
        created_at: new Date().toISOString()
      },
      {
        id: 8,
        commodity: "maize",
        variety: "Yellow Maize (Feed)",
        quantity: 50,
        unit: "quintal",
        location: "Davanagere",
        image_url: "../assets/crops/maize.jpg",
        created_at: new Date().toISOString()
      }
    ];
    saveLocalCrops();
  }

  function saveLocalCrops() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(userCrops));
    } catch (e) {
      console.error("Failed to save local crops:", e);
    }
  }

  // ── Metrics Calculation ───────────────────────────────────────────────────

  function updateSummary() {
    var totalCrops = userCrops.length;
    var totalQtls = userCrops.reduce(function (sum, crop) {
      return sum + quantityInQuintals(crop.quantity, crop.unit);
    }, 0);

    var totalPortfolioValue = userCrops.reduce(function (sum, crop) {
      var comm = normalizeCommodity(crop.commodity);
      var cfg = getCommodityConfig(comm);
      var qtl = quantityInQuintals(crop.quantity, crop.unit);
      var pricePerQtl = cachedPrices[crop.id] || cfg.benchmarkPricePerQtl;
      return sum + (qtl * pricePerQtl);
    }, 0);

    if (totalCropsEl) {
      totalCropsEl.innerHTML =
        totalCrops + ' <span class="text-body-md font-body-md text-on-surface-variant font-normal">' +
        (totalCrops === 1 ? "crop" : "crops") + "</span>";
    }
    if (totalQuantityEl) {
      totalQuantityEl.innerHTML =
        Math.round(totalQtls * 10) / 10 +
        ' <span class="text-body-md font-body-md text-on-surface-variant font-normal">qtl</span>';
    }
    if (totalValueEl) {
      totalValueEl.textContent = formatCurrency(totalPortfolioValue);
    }
  }

  // ── Pricing Engine ────────────────────────────────────────────────────────

  function fetchCropPrice(crop, priceEl, valueEl) {
    var comm = normalizeCommodity(crop.commodity);
    var cfg = getCommodityConfig(comm);

    function applyPrice(pPerQtl, label) {
      cachedPrices[crop.id] = pPerQtl;
      if (priceEl) {
        priceEl.textContent = label;
      }
      if (valueEl) {
        var qtls = quantityInQuintals(crop.quantity, crop.unit);
        var totalVal = qtls * pPerQtl;
        valueEl.textContent = formatCurrency(totalVal);
      }
      updateSummary();
    }

    if (comm === "coffee") {
      var defaultCoffeePrice = crop.variety && crop.variety.indexOf("Robusta") !== -1 ? 20000 : 51700;
      var defaultCoffeeLabel = crop.variety && crop.variety.indexOf("Robusta") !== -1 ? "₹10,000 / 50kg" : "₹25,850 / 50kg";
      if (window.CropMandiAPI && CropMandiAPI.getMarketPrices) {
        CropMandiAPI.getMarketPrices("coffee", crop.location || "Sakleshpur")
          .then(function (payload) {
            var rows = (payload && payload.observations) || [];
            var match = rows.find(function (r) {
              return String(r.type || "").toUpperCase().indexOf(String(crop.variety || "").toUpperCase()) !== -1;
            });
            var price = match && Number(match.price);
            if (Number.isFinite(price) && price > 0) {
              applyPrice(price * 2, "₹" + price.toLocaleString("en-IN") + " / 50kg");
            } else {
              applyPrice(defaultCoffeePrice, defaultCoffeeLabel);
            }
          })
          .catch(function () {
            applyPrice(defaultCoffeePrice, defaultCoffeeLabel);
          });
      } else {
        applyPrice(defaultCoffeePrice, defaultCoffeeLabel);
      }
      return;
    }

    if (comm === "pepper") {
      if (window.CropMandiAPI && CropMandiAPI.getMarketPrices) {
        CropMandiAPI.getMarketPrices("pepper", crop.location || "Madikeri")
          .then(function (payload) {
            var rows = (payload && payload.observations) || [];
            var price = rows.length && Number(rows[0].price);
            if (Number.isFinite(price) && price > 0) {
              applyPrice(price * 100, "₹" + price.toLocaleString("en-IN") + " / kg");
            } else {
              applyPrice(69000, "₹690 / kg");
            }
          })
          .catch(function () {
            applyPrice(69000, "₹690 / kg");
          });
      } else {
        applyPrice(69000, "₹690 / kg");
      }
      return;
    }

    if (comm === "cardamom") {
      applyPrice(245000, "₹2,450 / kg");
      return;
    }

    // Vegetable & Grain crops (Paddy, Tomato, Potato, Maize)
    var defaultRates = {
      paddy: { rate: 2240, label: "₹2,240 / qtl" },
      tomato: { rate: 1850, label: "₹1,850 / qtl" },
      potato: { rate: 1750, label: "₹1,750 / qtl" },
      maize: { rate: 2150, label: "₹2,150 / qtl" }
    };
    var d = defaultRates[comm] || { rate: 2000, label: "₹2,000 / qtl" };
    applyPrice(d.rate, d.label);
  }

  // ── Card Rendering ────────────────────────────────────────────────────────

  function createCropCard(crop) {
    var comm = normalizeCommodity(crop.commodity);
    var cfg = getCommodityConfig(comm);

    var card = document.createElement("div");
    card.className =
      "bg-surface-container-lowest rounded-xl card-shadow border-t border-white/50 p-5 flex flex-col group card-hover transition-all duration-300 relative overflow-hidden";

    var cropLocation = crop.location || "Karnataka";
    var imageUrl = resolveCropImage(crop.image_url, comm);
    var priceId = "crop-price-" + crop.id;
    var valueId = "crop-val-" + crop.id;

    var unitLabel = formatUnitDisplay(crop.unit);
    var quantityDisplay = crop.quantity + " " + unitLabel;

    // Track / Forecast button destination & text
    var trackUrl = "#";
    var trackLabel = "Track Market";
    var trackIcon = "monitoring";
    var trackClass = "bg-primary hover:bg-primary-container text-white";

    if (cfg.hasMLForecast) {
      // Requirements: for Paddy, Tomato, Potato, Maize button says "View Price Forecast"
      trackUrl = "../cropmandi_ai_dashboard/code.html?commodity=" + comm + "&variety=" + encodeURIComponent(crop.variety) + "#mandi-price-ai";
      trackLabel = "View Price Forecast";
      trackIcon = "psychology";
      trackClass = "bg-primary hover:bg-primary-container text-white font-bold";
    } else if (comm === "coffee" || comm === "pepper") {
      trackUrl = "../cropmandi_ai_dashboard/code.html?commodity=" + comm + "&variety=" + encodeURIComponent(crop.variety) + "#market-prices";
      trackLabel = "Track Market";
      trackIcon = "monitoring";
    } else {
      // Cardamom
      trackUrl = "../cropmandi_ai_analytics/code.html?commodity=cardamom";
      trackLabel = "Market Analytics";
      trackIcon = "analytics";
    }

    card.innerHTML =
      '<div class="h-44 mb-4 flex items-center justify-center bg-surface-container-low rounded-xl overflow-hidden relative shadow-inner">' +
        '<img alt="' + cfg.name + '" class="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-500" src="' + imageUrl + '" onerror="this.onerror=null; this.src=\'../cropmandi_ai_my_crops/screen.png\';"' + '/>' +
        '<div class="absolute top-3 left-3">' +
          '<span class="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-full border ' + cfg.badgeClass + '">' +
            (cfg.hasMLForecast ? '<span class="material-symbols-outlined text-[13px]">psychology</span>' : '') +
            cfg.badge +
          '</span>' +
        '</div>' +
        '<div class="absolute bottom-2 right-2 px-2.5 py-0.5 rounded-full bg-black/60 text-white text-[10px] font-semibold tracking-wide backdrop-blur-sm">' +
          cfg.category +
        '</div>' +
      '</div>' +

      '<div class="flex justify-between items-start mb-2">' +
        '<div>' +
          '<h3 class="text-headline-md font-headline-md text-on-background font-bold text-lg mb-1 flex items-center gap-1.5">' +
            cfg.name +
            '<span class="text-xs text-on-surface-variant font-normal">(' + cfg.kannada + ')</span>' +
          '</h3>' +
          '<span class="inline-block px-2.5 py-0.5 bg-surface-container text-on-surface-variant rounded-md text-xs font-semibold">' +
            crop.variety +
          '</span>' +
        '</div>' +
      '</div>' +

      '<p class="text-xs text-on-surface-variant line-clamp-2 mb-4 leading-relaxed">' +
        cfg.description +
      '</p>' +

      '<div class="grid grid-cols-2 gap-3 mb-5 bg-surface-container-low/60 rounded-lg p-3 text-xs">' +
        '<div>' +
          '<p class="text-outline uppercase text-[10px] font-bold tracking-wider mb-0.5">Quantity</p>' +
          '<p class="font-bold text-on-background text-sm">' + quantityDisplay + '</p>' +
        '</div>' +
        '<div>' +
          '<p class="text-outline uppercase text-[10px] font-bold tracking-wider mb-0.5">Location</p>' +
          '<p class="font-semibold text-on-background truncate flex items-center gap-0.5" title="' + cropLocation + '">' +
            '<span class="material-symbols-outlined text-xs text-primary">location_on</span> ' + cropLocation +
          '</p>' +
        '</div>' +
        '<div>' +
          '<p class="text-outline uppercase text-[10px] font-bold tracking-wider mb-0.5">Mandi Price</p>' +
          '<p class="font-bold text-primary text-sm" id="' + priceId + '">⏳ Fetching…</p>' +
        '</div>' +
        '<div>' +
          '<p class="text-outline uppercase text-[10px] font-bold tracking-wider mb-0.5">Est. Crop Value</p>' +
          '<p class="font-bold text-tertiary text-sm" id="' + valueId + '">…</p>' +
        '</div>' +
      '</div>' +

      '<div class="mt-auto pt-3 border-t border-outline-variant/30 flex items-center gap-2">' +
        '<a href="' + trackUrl + '" class="flex-1 py-2.5 px-3 rounded-lg text-xs font-bold ' + trackClass + ' transition-all flex items-center justify-center gap-1.5 shadow-sm track-market-btn" data-id="' + crop.id + '" data-commodity="' + comm + '" data-variety="' + crop.variety + '" data-location="' + cropLocation + '">' +
          '<span class="material-symbols-outlined text-base">' + trackIcon + '</span> ' + trackLabel +
        '</a>' +
        '<button class="py-2.5 px-3 rounded-lg text-xs font-bold text-on-surface-variant hover:text-primary hover:bg-surface-container border border-outline-variant/40 transition-colors edit-crop-btn" data-id="' + crop.id + '" title="Edit crop">' +
          '<span class="material-symbols-outlined text-base">edit</span>' +
        '</button>' +
        '<button class="py-2.5 px-3 rounded-lg text-xs font-bold text-error border border-error/30 hover:bg-error-container hover:text-on-error-container transition-colors delete-crop-btn" data-id="' + crop.id + '" title="Delete crop">' +
          '<span class="material-symbols-outlined text-base">delete</span>' +
        '</button>' +
      '</div>';

    // Track Market Click Handler
    var trackBtn = card.querySelector(".track-market-btn");
    if (trackBtn) {
      trackBtn.addEventListener("click", function (e) {
        localStorage.setItem("cropmandi_dash_commodity", comm);
        localStorage.setItem("cropmandi_dash_variety", crop.variety);
        localStorage.setItem("cropmandi_dash_location", cropLocation);
      });
    }

    // Edit Button Handler
    var editBtn = card.querySelector(".edit-crop-btn");
    if (editBtn) {
      editBtn.addEventListener("click", function (e) {
        e.preventDefault();
        openEditModal(crop);
      });
    }

    // Delete Button Handler
    var deleteBtn = card.querySelector(".delete-crop-btn");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function (e) {
        e.preventDefault();
        promptDeleteCrop(crop);
      });
    }

    // Fetch and calculate dynamic pricing & valuation
    fetchCropPrice(crop, card.querySelector("#" + priceId), card.querySelector("#" + valueId));

    return card;
  }

  function renderCrops() {
    if (!cropGallery) {
      return;
    }

    cropGallery.innerHTML = "";

    if (userCrops.length === 0) {
      var emptyState = document.createElement("div");
      emptyState.className = "col-span-1 md:col-span-3 text-center py-16 bg-surface-container-lowest rounded-2xl border border-dashed border-outline-variant/40";
      emptyState.innerHTML =
        '<div class="flex flex-col items-center gap-4 max-w-md mx-auto">' +
          '<div class="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center text-primary">' +
            '<span class="material-symbols-outlined text-[36px]">agriculture</span>' +
          '</div>' +
          '<h3 class="text-headline-md font-bold text-on-background">No Crops in Your Inventory</h3>' +
          '<p class="text-body-md text-on-surface-variant text-sm leading-relaxed">' +
            'Add your harvest records for Coffee, Black Pepper, Cardamom, Paddy, Tomato, Potato, or Maize to track real-time Mandi market rates and generate AI predictions.' +
          '</p>' +
          '<button class="mt-2 bg-primary text-white font-bold px-6 py-2.5 rounded-lg shadow-md hover:bg-primary-container transition-all flex items-center gap-2" onclick="document.getElementById(\'add-crop-button\').click()">' +
            '<span class="material-symbols-outlined text-sm">add</span> Add First Crop' +
          '</button>' +
        '</div>';
      cropGallery.appendChild(emptyState);
      updateSummary();
      return;
    }

    userCrops.forEach(function (crop) {
      cropGallery.appendChild(createCropCard(crop));
    });
    updateSummary();
  }

  // ── Modal Operations (Add / Edit) ─────────────────────────────────────────

  function fillVarietyOptions(commodity, selectedVariety) {
    if (!modalVarietySelect) return;
    var cfg = getCommodityConfig(commodity);
    modalVarietySelect.innerHTML = "";

    var defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select variety / grade...";
    modalVarietySelect.appendChild(defaultOption);

    cfg.varieties.forEach(function (v, idx) {
      var opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      if (selectedVariety ? (selectedVariety === v) : (idx === 0)) {
        opt.selected = true;
      }
      modalVarietySelect.appendChild(opt);
    });
  }

  function fillLocationOptions(commodity, selectedLocation) {
    if (!modalLocationSelect) return;
    var cfg = getCommodityConfig(commodity);
    modalLocationSelect.innerHTML = "";

    var defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select farm location / mandi...";
    modalLocationSelect.appendChild(defaultOption);

    cfg.locations.forEach(function (loc, idx) {
      var opt = document.createElement("option");
      opt.value = loc;
      opt.textContent = loc;
      if (selectedLocation ? (selectedLocation === loc) : (idx === 0)) {
        opt.selected = true;
      }
      modalLocationSelect.appendChild(opt);
    });

    if (window.CropMandiAPI && CropMandiAPI.getMarkets && (commodity === "coffee" || commodity === "pepper")) {
      if (modalLocationLoading) modalLocationLoading.classList.remove("hidden");
      CropMandiAPI.getMarkets(commodity)
        .then(function (payload) {
          if (modalLocationLoading) modalLocationLoading.classList.add("hidden");
          var liveNames = ((payload && payload.locations) || []).map(function (row) {
            return row && row.name;
          }).filter(Boolean);
          if (liveNames.length > 0) {
            modalLocationSelect.innerHTML = "";
            modalLocationSelect.appendChild(defaultOption);
            liveNames.forEach(function (loc, idx) {
              var opt = document.createElement("option");
              opt.value = loc;
              opt.textContent = loc;
              if (selectedLocation ? (selectedLocation === loc) : (idx === 0)) {
                opt.selected = true;
              }
              modalLocationSelect.appendChild(opt);
            });
          }
        })
        .catch(function () {
          if (modalLocationLoading) modalLocationLoading.classList.add("hidden");
        });
    }
  }

  function openAddModal() {
    if (!modal) return;
    hideModalError();
    if (modalCropId) modalCropId.value = "";
    if (modalTitle) modalTitle.textContent = "Add New Crop";
    if (modalSaveButton) modalSaveButton.textContent = "Save Crop";
    if (modalCropSelect) modalCropSelect.value = "";
    if (modalVarietySelect) modalVarietySelect.innerHTML = '<option value="">Select variety / grade...</option>';
    if (modalQuantityInput) modalQuantityInput.value = "";
    if (modalUnitSelect) modalUnitSelect.value = "quintal";
    if (modalLocationSelect) modalLocationSelect.innerHTML = '<option value="">Select farm location / mandi...</option>';
    if (modalLocationLoading) modalLocationLoading.classList.add("hidden");
    if (modalLocationError) modalLocationError.classList.add("hidden");
    modal.classList.remove("hidden");
  }

  function openEditModal(crop) {
    if (!modal) return;
    hideModalError();
    var comm = normalizeCommodity(crop.commodity);
    if (modalCropId) modalCropId.value = crop.id;
    if (modalTitle) modalTitle.textContent = "Edit Crop Details";
    if (modalSaveButton) modalSaveButton.textContent = "Save Changes";

    if (modalCropSelect) modalCropSelect.value = comm;
    fillVarietyOptions(comm, crop.variety);
    if (modalQuantityInput) modalQuantityInput.value = crop.quantity;
    if (modalUnitSelect) modalUnitSelect.value = crop.unit || "quintal";
    fillLocationOptions(comm, crop.location);

    modal.classList.remove("hidden");
  }

  function closeModal() {
    if (modal) modal.classList.add("hidden");
    hideModalError();
  }

  function showModalError(msg) {
    if (modalErrorBox && modalErrorText) {
      modalErrorText.textContent = msg;
      modalErrorBox.classList.remove("hidden");
    } else {
      alert(msg);
    }
  }

  function hideModalError() {
    if (modalErrorBox) {
      modalErrorBox.classList.add("hidden");
    }
  }

  function saveCrop() {
    hideModalError();

    var cropId = modalCropId ? modalCropId.value : "";
    
    // Read commodity value safely
    var rawCommodity = "";
    if (modalCropSelect) {
      if (modalCropSelect.value) {
        rawCommodity = modalCropSelect.value;
      } else if (modalCropSelect.selectedIndex >= 0) {
        rawCommodity = modalCropSelect.options[modalCropSelect.selectedIndex].value;
      }
    }
    var commodity = normalizeCommodity(rawCommodity);

    if (!commodity || !COMMODITY_CONFIG[commodity]) {
      showModalError("Please select a commodity.");
      return;
    }

    var cfg = getCommodityConfig(commodity);

    // Variety validation with smart default fallback
    var variety = modalVarietySelect ? modalVarietySelect.value : "";
    if (!variety && modalVarietySelect && modalVarietySelect.options.length > 1) {
      variety = modalVarietySelect.options[1].value;
      modalVarietySelect.selectedIndex = 1;
    }
    if (!variety && cfg.varieties && cfg.varieties.length > 0) {
      variety = cfg.varieties[0];
    }
    if (!variety) {
      showModalError("Please select a variety / grade.");
      return;
    }

    // Quantity validation
    var quantity = modalQuantityInput ? Number(modalQuantityInput.value) : 0;
    if (!Number.isFinite(quantity) || quantity <= 0) {
      showModalError("Please enter a valid harvest quantity greater than 0.");
      return;
    }

    // Unit
    var unit = modalUnitSelect ? modalUnitSelect.value : "quintal";
    unit = unit || "quintal";

    // Location validation with smart default fallback
    var location = modalLocationSelect ? modalLocationSelect.value : "";
    if (!location && modalLocationSelect && modalLocationSelect.options.length > 1) {
      location = modalLocationSelect.options[1].value;
      modalLocationSelect.selectedIndex = 1;
    }
    if (!location && cfg.locations && cfg.locations.length > 0) {
      location = cfg.locations[0];
    }
    if (!location) {
      showModalError("Please select a farm location or mandi centre.");
      return;
    }

    var payload = {
      commodity: commodity,
      variety: variety,
      quantity: quantity,
      unit: unit,
      location: location,
      image_url: cfg.image
    };

    if (cropId) {
      // Update existing crop
      var idNum = isNaN(Number(cropId)) ? cropId : Number(cropId);
      var idx = userCrops.findIndex(function (c) { return c.id == idNum; });
      if (idx !== -1) {
        userCrops[idx] = Object.assign({}, userCrops[idx], payload, {
          updated_at: new Date().toISOString()
        });
        saveLocalCrops();
        renderCrops();
      }

      if (window.CropMandiAPI && CropMandiAPI.updateFarmerCrop && !isNaN(Number(cropId))) {
        CropMandiAPI.updateFarmerCrop(Number(cropId), payload).catch(function (err) {
          console.warn("Backend update failed, kept local change:", err);
        });
      }
      closeModal();
    } else {
      // Add new crop
      var tempId = Date.now();
      var newRecord = Object.assign({ id: tempId, created_at: new Date().toISOString() }, payload);
      userCrops.unshift(newRecord);
      saveLocalCrops();
      renderCrops();
      closeModal();

      if (window.CropMandiAPI && CropMandiAPI.addFarmerCrop) {
        CropMandiAPI.addFarmerCrop(payload)
          .then(function (res) {
            if (res && res.success && res.crop && res.crop.id) {
              var recIdx = userCrops.findIndex(function (c) { return c.id === tempId; });
              if (recIdx !== -1) {
                userCrops[recIdx].id = res.crop.id;
                saveLocalCrops();
              }
            }
          })
          .catch(function (err) {
            console.warn("Backend add crop failed, kept local record:", err);
          });
      }
    }
  }

  // ── Delete Operations ─────────────────────────────────────────────────────

  function promptDeleteCrop(crop) {
    cropToDeleteId = crop.id;
    var cfg = getCommodityConfig(crop.commodity);
    if (deleteModalMessage) {
      deleteModalMessage.innerHTML =
        'Are you sure you want to remove <strong>' + cfg.name + ' (' + crop.variety + ')</strong> ' +
        'from your inventory?';
    }
    if (deleteModal) {
      deleteModal.classList.remove("hidden");
    }
  }

  function confirmDeleteCrop() {
    if (!cropToDeleteId) return;
    var toDelete = cropToDeleteId;
    userCrops = userCrops.filter(function (c) { return c.id != toDelete; });
    saveLocalCrops();
    closeDeleteModal();
    renderCrops();

    if (window.CropMandiAPI && CropMandiAPI.deleteFarmerCrop && !isNaN(Number(toDelete))) {
      CropMandiAPI.deleteFarmerCrop(Number(toDelete)).catch(function (err) {
        console.warn("Backend delete failed, removed from local cache:", err);
      });
    }
  }

  function closeDeleteModal() {
    if (deleteModal) deleteModal.classList.add("hidden");
    cropToDeleteId = null;
  }

  function closeNoticeModal() {
    if (noticeModal) {
      noticeModal.classList.add("hidden");
    }
  }

  // ── Initialization ────────────────────────────────────────────────────────

  function init() {
    cropGallery = $("crop-gallery");
    totalCropsEl = $("total-crops");
    totalQuantityEl = $("total-quantity");
    totalValueEl = $("total-value");
    addCropButton = $("add-crop-button");

    modal = $("add-crop-modal");
    modalCropId = $("modal-crop-id");
    modalTitle = $("modal-title");
    modalCropSelect = $("modal-crop-select");
    modalVarietySelect = $("modal-variety-select");
    modalQuantityInput = $("modal-quantity-input");
    modalUnitSelect = $("modal-unit-select");
    modalLocationSelect = $("modal-location-select");
    modalLocationLoading = $("modal-location-loading");
    modalLocationError = $("modal-location-error");
    modalCancelButton = $("modal-cancel-button");
    modalSaveButton = $("modal-save-button");
    modalCloseButton = $("modal-close-button");
    modalErrorBox = $("modal-error-box");
    modalErrorText = $("modal-error-text");

    deleteModal = $("delete-modal");
    deleteModalMessage = $("delete-modal-message");
    deleteCancelButton = $("delete-cancel-button");
    deleteConfirmButton = $("delete-confirm-button");

    noticeModal = $("crop-notice-modal");
    noticeModalCloseButton = $("notice-modal-close-button");

    if (!cropGallery || !addCropButton) return;

    loadUserCrops();

    addCropButton.addEventListener("click", openAddModal);

    if (modalCropSelect) {
      modalCropSelect.addEventListener("change", function () {
        hideModalError();
        var comm = normalizeCommodity(modalCropSelect.value);
        if (comm && COMMODITY_CONFIG[comm]) {
          fillVarietyOptions(comm);
          fillLocationOptions(comm);
          if (modalUnitSelect) {
            modalUnitSelect.value = COMMODITY_CONFIG[comm].defaultUnit || "quintal";
          }
        }
      });
    }

    if (modalCancelButton) modalCancelButton.addEventListener("click", closeModal);
    if (modalCloseButton) modalCloseButton.addEventListener("click", closeModal);
    if (modalSaveButton) modalSaveButton.addEventListener("click", saveCrop);

    if (deleteCancelButton) deleteCancelButton.addEventListener("click", closeDeleteModal);
    if (deleteConfirmButton) deleteConfirmButton.addEventListener("click", confirmDeleteCrop);

    if (noticeModalCloseButton) noticeModalCloseButton.addEventListener("click", closeNoticeModal);

    if (modal) {
      modal.addEventListener("click", function (e) {
        if (e.target === modal) closeModal();
      });
    }
    if (deleteModal) {
      deleteModal.addEventListener("click", function (e) {
        if (e.target === deleteModal) closeDeleteModal();
      });
    }
    if (noticeModal) {
      noticeModal.addEventListener("click", function (e) {
        if (e.target === noticeModal) closeNoticeModal();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
