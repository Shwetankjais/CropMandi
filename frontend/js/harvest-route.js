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

  var statusEl = document.getElementById("form-status");
  var resultsEl = document.getElementById("results");
  var planBtn = document.getElementById("plan-btn");
  var mapStatusEl = document.getElementById("map-status");

  var map = null;
  var mapLayers = null;
  var marketMarkers = {};

  var routeColors = [
    "#2376c8",
    "#8855b7",
    "#d58a20",
    "#168a79",
    "#c34e67"
  ];


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

    statusEl.className =
      "status" + (isError ? " error" : "");
  }


  function setMapStatus(message, isError) {

    if (!mapStatusEl) return;

    mapStatusEl.textContent = message || "";

    mapStatusEl.className =
      "map-status" + (isError ? " error" : "");
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

          series.innerHTML =
            '<option value="">No variety/grade data found</option>';

          return;
        }

        options.forEach(function (option, index) {

          var item = document.createElement("option");

          item.value = option.value;

          item.textContent =
            option.label || option.value;

          if (index === 0) {
            item.selected = true;
          }

          series.appendChild(item);

        });

      })

      .catch(function (error) {

        series.innerHTML =
          '<option value="">Could not load varieties</option>';

        setStatus(error.message, true);

      });

  }


  /* =========================================
     INITIALIZE LEAFLET MAP
  ========================================= */

  function initMap() {

    if (map) return true;

    var mapElement =
      document.getElementById("harvest-map");

    if (!window.L || !mapElement) {

      setMapStatus(
        "Leaflet did not load. Check your internet connection, Leaflet CDN requests and the map container.",
        true
      );

      console.error(
        "Leaflet library or harvest-map container is missing."
      );

      return false;
    }

    try {

      map = window.L.map(
        "harvest-map",
        {
          scrollWheelZoom: false
        }
      ).setView(
        [13.05, 76.0],
        7
      );

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
          "The map loaded but some map tiles could not be retrieved. Check your internet connection or tile-service access.",
          true
        );

      });

      tiles.on("load", function () {

        setMapStatus(
          "OpenStreetMap loaded. Submit your farm details to display recommended market routes."
        );

      });

      mapLayers =
        window.L.layerGroup().addTo(map);

      window.setTimeout(function () {

        if (map) {
          map.invalidateSize();
        }

      }, 250);

      console.log(
        "CropMandi Harvest Route map initialized successfully."
      );

      return true;

    } catch (error) {

      console.error("Map initialization error:", error);

      setMapStatus(
        "The interactive map could not be initialized: " +
        error.message,
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

      html:
        '<span class="cm-map-pin ' +
        kind +
        '">' +
        escapeHtml(label) +
        '</span>',

      iconSize: [28, 28],

      iconAnchor: [14, 14],

      popupAnchor: [0, -13]

    });

  }


  /* =========================================
     VALIDATE COORDINATES
  ========================================= */

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

    var bounds = [];

    var origin = data.origin_coordinates;

    var markerCount = 0;

    var routeCount = 0;

    var markets = data.markets || [];


    /* FARM MARKER */

    if (validLatLng(origin)) {

      var originPoint = [
        Number(origin[0]),
        Number(origin[1])
      ];

      window.L.marker(

        originPoint,

        {
          icon: makePin("farm", "F"),
          title: "Farm location"
        }

      )

        .bindPopup(
          "<strong>Farm location</strong><br>" +
          escapeHtml(data.origin || "Your farm")
        )

        .addTo(mapLayers);


      bounds.push(originPoint);

      markerCount += 1;

    }


    /* MARKET MARKERS AND ROAD ROUTES */

    markets.forEach(function (market, index) {

      var destination =
        market.destination_coordinates;

      var color =
        routeColors[index % routeColors.length];


      /* MARKET MARKER */

      if (validLatLng(destination)) {

        var destinationPoint = [

          Number(destination[0]),

          Number(destination[1])

        ];

        var marker = window.L.marker(

          destinationPoint,

          {
            icon: makePin(
              "market",
              String(index + 1)
            ),

            title:
              market.market_name ||
              market.town ||
              "Recommended market"
          }

        )

          .bindPopup(

            "<strong>" +
            escapeHtml(
              market.market_name ||
              market.town ||
              "Market"
            ) +
            "</strong><br>" +

            escapeHtml(market.town || "") +

            (
              market.distance_km == null
                ? ""
                : "<br>Road distance: " +
                  escapeHtml(market.distance_km) +
                  " km"
            )

          )

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

        var line = window.L.geoJSON(

          geometry,

          {

            style: {

              color: color,

              weight: 5,

              opacity: 0.82,

              lineCap: "round",

              lineJoin: "round"

            }

          }

        ).addTo(mapLayers);


        if (
          line.getBounds &&
          line.getBounds().isValid()
        ) {

          var lineBounds =
            line.getBounds();

          bounds.push(
            lineBounds.getSouthWest(),
            lineBounds.getNorthEast()
          );

        }

        routeCount += 1;

      }

    });


    /* AUTOMATIC MAP ZOOM */

    if (bounds.length) {

      map.fitBounds(

        window.L.latLngBounds(bounds),

        {
          padding: [28, 28],
          maxZoom: 11
        }

      );

    } else {

      map.setView(
        [13.05, 76.0],
        7
      );

    }


    window.setTimeout(function () {

      if (map) {
        map.invalidateSize();
      }

    }, 100);


    /* MAP STATUS */

    if (!markerCount) {

      setMapStatus(
        "No mapped coordinates were returned. Check the farm location and try again.",
        true
      );

    } else if (!routeCount) {

      setMapStatus(

        markerCount +
        " farm/market location marker(s) plotted. Road geometry was unavailable for these destinations; use the driving-directions links below."

      );

    } else {

      setMapStatus(

        "Showing " +
        routeCount +
        " road route(s) and " +
        markerCount +
        " location marker(s). Routes are indicative town-centre routes, not verified trader-gate navigation."

      );

    }

  }


  /* =========================================
     FOCUS ON SELECTED MARKET
  ========================================= */

  function focusMarket(index) {

    if (!map || !marketMarkers[index]) return;

    var marker = marketMarkers[index];

    map.setView(

      marker.getLatLng(),

      12,

      {
        animate: true
      }

    );

    marker.openPopup();

  }


  /* =========================================
     RENDER MARKET CARDS
  ========================================= */

  function render(data) {

    var markets = data.markets || [];

    document.getElementById(
      "results-subtitle"
    ).textContent =

      data.commodity +
      " · " +
      (data.selected_series || "all available grades") +
      " · " +
      data.quantity_kg +
      " kg";


    /* Render map */

    renderMap(data);


    if (!markets.length) {

      resultsEl.innerHTML =
        '<div class="empty">No suitable market routes were returned. Try another crop or origin.</div>';

      return;
    }


    /* Generate market cards */

    resultsEl.innerHTML = markets.map(

      function (market, index) {

        var valueStats = [

          [
            "Road distance",

            market.distance_km == null
              ? "Unavailable"
              : market.distance_km + " km"
          ],

          [
            "Travel time",

            market.duration_min == null
              ? "Unavailable"
              : Math.round(market.duration_min) + " min"
          ],

          [
            "Observed price",

            rupees(market.price) +
            (
              market.unit
                ? " / " + escapeHtml(market.unit)
                : ""
            )
          ],

          [
            "Gross estimate",
            rupees(market.gross_estimate_inr)
          ],

          [
            "Transport estimate",
            rupees(market.transport_estimate_inr)
          ],

          [
            "Net estimate",
            rupees(market.net_estimate_inr)
          ]

        ];


        return (

          '<article class="market">' +

            '<div class="market-top">' +

              '<div>' +

                '<h3>' +
                escapeHtml(
                  market.market_name ||
                  market.town ||
                  "Market"
                ) +
                '</h3>' +

                '<small>' +
                escapeHtml(
                  market.town ||
                  "Town location unavailable"
                ) +
                '</small>' +

              '</div>' +

              '<span class="rank">Recommended #' +
              escapeHtml(market.recommendation_order) +
              '</span>' +

            '</div>' +


            '<div class="stats">' +

              valueStats.map(function (stat) {

                return (

                  '<div class="stat">' +

                    '<span>' +
                    stat[0] +
                    '</span>' +

                    '<strong>' +
                    stat[1] +
                    '</strong>' +

                  '</div>'

                );

              }).join("") +

            '</div>' +


            '<div class="market-foot">' +

              '<small>' +

                'Price date: ' +

                escapeHtml(
                  market.price_date || "Not provided"
                ) +

                ' · ' +

                escapeHtml(
                  market.price_freshness ||
                  "Freshness unknown"
                ) +

              '</small>' +


              '<div class="actions">' +

                '<button type="button" class="map-focus" data-map-focus="' +
                index +
                '">' +

                  'Locate on map' +

                '</button>' +


                '<a href="' +
                escapeHtml(market.route_url) +
                '" target="_blank" rel="noopener">' +

                  'Open driving directions ↗' +

                '</a>' +

              '</div>' +

            '</div>' +

          '</article>'

        );

      }

    ).join("");


    /* Attach map focus buttons */

    Array.prototype.forEach.call(

      resultsEl.querySelectorAll("[data-map-focus]"),

      function (button) {

        button.addEventListener("click", function () {

          focusMarket(
            Number(
              button.getAttribute("data-map-focus")
            )
          );

        });

      }

    );


    /* Display limitations */

    var notes =
      (data.limitations || []).join(" ");

    if (data.unit_note) {

      notes =
        data.unit_note + " " + notes;

    }

    var box =
      document.getElementById("limitations");

    box.hidden = !notes;

    box.textContent = notes;

  }


  /* =========================================
     EVENT LISTENERS
  ========================================= */

  commodity.addEventListener(
    "change",
    loadSeries
  );


  originInput.addEventListener(
    "input",
    function () {
      coords = null;
    }
  );


  /* GPS BUTTON */

  document.getElementById("gps-btn")

    .addEventListener("click", function () {

      if (!navigator.geolocation) {

        setStatus(
          "This browser does not support GPS location.",
          true
        );

        return;

      }


      setStatus(
        "Requesting location permission…"
      );


      navigator.geolocation.getCurrentPosition(

        function (position) {

          coords = {

            latitude: position.coords.latitude,

            longitude: position.coords.longitude

          };


          originInput.value =
            "My current farm location";


          setStatus(
            "GPS location captured for this calculation."
          );

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


  /* =========================================
     HARVEST ROUTE FORM SUBMISSION
  ========================================= */

  form.addEventListener(
    "submit",
    function (event) {

      event.preventDefault();


      var payload = {

        commodity: commodity.value,

        series: series.value || null,

        origin: originInput.value.trim(),

        quantity_kg:
          Number(
            document.getElementById("quantity").value
          ),

        transport_cost_per_km:
          Number(
            document.getElementById("cost").value
          ),

        limit: 5

      };


      if (coords) {

        payload.latitude =
          coords.latitude;

        payload.longitude =
          coords.longitude;

      }


      if (

        !payload.origin ||

        !(payload.quantity_kg > 0) ||

        !(payload.transport_cost_per_km >= 0)

      ) {

        setStatus(
          "Please check the farm location, harvest quantity and transport cost.",
          true
        );

        return;

      }


      planBtn.disabled = true;

      planBtn.textContent =
        "Calculating routes…";


      setStatus(
        "Comparing market prices and requesting indicative road routes. First-time town lookups may take a few seconds."
      );


      setMapStatus(
        "Looking up the farm and market coordinates and plotting available road routes…"
      );


      resultsEl.innerHTML =
        '<div class="empty">Calculating market and route options…</div>';


      var routeRequest =

        window.CropMandiAPI &&
        window.CropMandiAPI.planHarvestRoutes

          ? window.CropMandiAPI.planHarvestRoutes(payload)

          : fetch(

              apiUrl("/api/harvest/routes"),

              {

                method: "POST",

                headers: {

                  "Content-Type": "application/json",

                  "Accept": "application/json"

                },

                body: JSON.stringify(payload)

              }

            )

            .then(function (response) {

              return response.json().then(function (body) {

                if (!response.ok) {

                  throw new Error(
                    body.detail ||
                    body.message ||
                    "Route calculation failed"
                  );

                }

                return body;

              });

            });


      routeRequest

        .then(function (data) {

          render(data);

          setStatus(
            "Comparison generated. Confirm the latest rate and route with the market before dispatch."
          );

        })


        .catch(function (error) {

          console.error(
            "Harvest Route request failed:",
            error
          );

          resultsEl.innerHTML =
            '<div class="empty">' +
            escapeHtml(error.message) +
            '</div>';


          setStatus(
            error.message,
            true
          );


          setMapStatus(

            "The route could not be plotted because the route request failed: " +
            error.message,

            true

          );

        })


        .finally(function () {

          planBtn.disabled = false;

          planBtn.textContent =
            "Compare markets & routes";

        });

    }

  );


  /* =========================================
     PAGE INITIALIZATION
  ========================================= */

  initMap();

  loadSeries();

})();