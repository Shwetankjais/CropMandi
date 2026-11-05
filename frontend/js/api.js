/**
 * Shared CropMandi AI API helper.
 */
(function (global) {
  "use strict";

  var API_BASE_URL = "http://127.0.0.1:8001";

  var API_PATHS = {
    latestPrices: "/api/prices/latest",
    priceHistory: "/api/prices/history",
    nextSessionEstimate: "/api/predictions/next",
    markets: "/api/markets",
    marketCentres: "/api/markets/centres",
    marketAvailable: "/api/markets/available",
    marketPrices: "/api/markets/prices",
    marketRankings: "/api/markets/rankings",
    analytics: "/api/analytics",
    weather: "/api/weather",
    coldStorages: "/api/cold-storages",
    coldStorageByLocation: "/api/cold-storage",
    paymentCreateOrder: "/api/payment/create-order",
    paymentVerify: "/api/payment/verify",
    paymentHistory: "/api/payment/history",
    paymentStatus: "/api/payment/status",
    paymentCancel: "/api/payment/cancel",
    commoditiesList: "/api/commodities/list",
    commodityOptions: "/api/commodities/options",
    predictPrice: "/api/predictions/price",
    predictionHistory: "/api/predictions/history",
    harvestRoutes: "/api/harvest/routes",
    harvestVehicles: "/api/harvest/vehicles",
    harvestFuelPrice: "/api/harvest/fuel-price",
    farmerCrops: "/api/farmer/crops",
    farmerCropsMetadata: "/api/farmer/crops/metadata",
  };

  function endpoint(path, query) {
    var url = API_BASE_URL + path;
    if (!query) {
      return url;
    }
    var parts = [];
    Object.keys(query).forEach(function (key) {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(query[key]));
      }
    });
    return parts.length ? url + "?" + parts.join("&") : url;
  }

  function parseJsonBody(res) {
    return res.text().then(function (text) {
      var body = {};
      if (text && String(text).trim()) {
        try {
          body = JSON.parse(text);
        } catch (parseErr) {
          var err = new Error("Could not read the API response");
          err.status = res.status;
          throw err;
        }
      }
      if (!res.ok) {
        var message = (body && (body.message || body.error || body.detail)) || "Request failed";
        var fail = new Error(message);
        fail.status = res.status;
        fail.code = body && body.error;
        throw fail;
      }
      return body;
    });
  }

  function getJson(path, query) {
    return fetch(endpoint(path, query)).then(parseJsonBody);
  }

  function postJson(path, payload) {
    return fetch(endpoint(path), {
      method: "POST",
      mode: "cors",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload || {}),
    }).then(parseJsonBody);
  }

  function getLatestPrices(commodity) {
    return getJson(API_PATHS.latestPrices, { commodity: commodity });
  }

  function getPriceHistory(commodity, series) {
    return getJson(API_PATHS.priceHistory, {
      commodity: commodity,
      series: series,
    });
  }

  function getMarkets(commodity) {
    return getJson(API_PATHS.markets, { commodity: commodity });
  }

  function getMarketCentres(commodity, location) {
    return getJson(API_PATHS.marketCentres, {
      commodity: commodity,
      location: location,
    });
  }

  function getMarketAvailable(commodity, location) {
    return getJson(API_PATHS.marketAvailable, {
      commodity: commodity,
      location: location,
    });
  }

  function getMarketPrices(commodity, location) {
    return getJson(API_PATHS.marketPrices, {
      commodity: commodity,
      location: location,
    });
  }

  function getMarketPricesHistory(commodity, location) {
    return getJson(API_PATHS.marketPrices, {
      commodity: commodity,
      location: location,
    });
  }

  function getMarketRankings(commodity, series, limit) {
    return getJson(API_PATHS.marketRankings, {
      commodity: commodity,
      series: series,
      limit: limit || 5,
    });
  }

  function getNextSessionEstimate(commodity, series) {
    return getJson(API_PATHS.nextSessionEstimate, {
      commodity: commodity,
      series: series,
    });
  }

  function getWeather(location) {
    return getJson(API_PATHS.weather, { location: location });
  }

  function getAnalytics(commodity, location, days) {
    return getJson(API_PATHS.analytics, {
      commodity: commodity,
      location: location,
      days: days,
    });
  }

  function getColdStorages(query) {
    return getJson(API_PATHS.coldStorages, query);
  }

  function getColdStorageByLocation(location, limit) {
    return getJson(API_PATHS.coldStorageByLocation, {
      location: location,
      limit: limit,
    });
  }

  function createPaymentOrder(payload) {
    return postJson(API_PATHS.paymentCreateOrder, payload);
  }

  function verifyPayment(payload) {
    return postJson(API_PATHS.paymentVerify, payload);
  }

  function getPaymentHistory() {
    return getJson(API_PATHS.paymentHistory);
  }

  function getPaymentStatus(orderId) {
    return getJson(API_PATHS.paymentStatus + "/" + encodeURIComponent(orderId));
  }

  function cancelPayment(orderId) {
    return postJson(API_PATHS.paymentCancel, { razorpay_order_id: orderId });
  }

  function getCommoditiesList() {
    return getJson(API_PATHS.commoditiesList);
  }

  function getCommodityOptions(commodity) {
    return getJson(API_PATHS.commodityOptions, { commodity: commodity });
  }

  function predictPrice(payload) {
    return postJson(API_PATHS.predictPrice, payload);
  }

  function getPredictionHistory(userId, commodity, limit) {
    return getJson(API_PATHS.predictionHistory, {
      user_id: userId || "default_farmer",
      commodity: commodity,
      limit: limit || 20,
    });
  }

  function planHarvestRoutes(payload) {
    return postJson(API_PATHS.harvestRoutes, payload);
  }

  function getHarvestVehicles() {
    return getJson(API_PATHS.harvestVehicles);
  }

  function getHarvestFuelPrice() {
    return getJson(API_PATHS.harvestFuelPrice);
  }

  function getFarmerCrops() {
    return getJson(API_PATHS.farmerCrops);
  }

  function addFarmerCrop(payload) {
    return postJson(API_PATHS.farmerCrops, payload);
  }

  function updateFarmerCrop(cropId, payload) {
    return fetch(endpoint(API_PATHS.farmerCrops + "/" + encodeURIComponent(cropId)), {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload || {}),
    }).then(parseJsonBody);
  }

  function deleteFarmerCrop(cropId) {
    return fetch(endpoint(API_PATHS.farmerCrops + "/" + encodeURIComponent(cropId)), {
      method: "DELETE",
      headers: { Accept: "application/json" },
    }).then(parseJsonBody);
  }

  function getCropMetadata() {
    return getJson(API_PATHS.farmerCropsMetadata);
  }

  global.CropMandiAPI = {
    baseUrl: API_BASE_URL,
    paths: API_PATHS,
    endpoint: endpoint,
    getJson: getJson,
    getLatestPrices: getLatestPrices,
    getPriceHistory: getPriceHistory,
    getMarkets: getMarkets,
    getMarketCentres: getMarketCentres,
    getMarketAvailable: getMarketAvailable,
    getMarketPrices: getMarketPrices,
    getMarketPricesHistory: getMarketPricesHistory,
    getMarketRankings: getMarketRankings,
    getNextSessionEstimate: getNextSessionEstimate,
    getWeather: getWeather,
    getAnalytics: getAnalytics,
    getColdStorages: getColdStorages,
    getColdStorageByLocation: getColdStorageByLocation,
    postJson: postJson,
    createPaymentOrder: createPaymentOrder,
    verifyPayment: verifyPayment,
    getPaymentHistory: getPaymentHistory,
    getPaymentStatus: getPaymentStatus,
    cancelPayment: cancelPayment,
    getCommoditiesList: getCommoditiesList,
    getCommodityOptions: getCommodityOptions,
    predictPrice: predictPrice,
    getPredictionHistory: getPredictionHistory,
    planHarvestRoutes: planHarvestRoutes,
    getHarvestVehicles: getHarvestVehicles,
    getHarvestFuelPrice: getHarvestFuelPrice,
    getFarmerCrops: getFarmerCrops,
    addFarmerCrop: addFarmerCrop,
    updateFarmerCrop: updateFarmerCrop,
    deleteFarmerCrop: deleteFarmerCrop,
    getCropMetadata: getCropMetadata,
  };
})(window);
