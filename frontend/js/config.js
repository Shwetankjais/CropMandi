/* CropMandi runtime configuration.
 * Edit apiBaseUrl below when the API runs on a different host.
 * Examples:
 *   Same computer: leave blank (auto-detected as the current host on port 8001).
 *   Separate API host: apiBaseUrl: "https://api.example.com"
 *   LAN server: apiBaseUrl: "http://192.168.1.20:8001" (microphone needs HTTPS on non-localhost pages).
 */
(function (global) {
  "use strict";

  // Set this to an explicit API origin when frontend and backend are hosted separately.
  // Example: "https://api.cropmandi.example.com"
  var API_BASE_URL_OVERRIDE = "";
  var existing = global.CropMandiConfig || {};
  var explicitBase = String(API_BASE_URL_OVERRIDE || existing.apiBaseUrl || global.CROPMANDI_API_BASE_URL || "").trim();

  function inferBaseUrl() {
    var hostname = (global.location && global.location.hostname) || "127.0.0.1";
    var pageProtocol = (global.location && global.location.protocol) || "http:";
    var protocol = pageProtocol === "https:" ? "https:" : "http:";
    if (!hostname || hostname === "") hostname = "127.0.0.1";
    // For the default setup, frontend and backend share a host. On HTTPS pages,
    // the API must also be served over HTTPS by a reverse proxy or TLS-enabled server.
    return protocol + "//" + hostname + ":8001";
  }

  var base = (explicitBase || inferBaseUrl()).replace(/\/+$/, "");
  function apiUrl(path) {
    var suffix = String(path || "");
    if (suffix && suffix.charAt(0) !== "/") suffix = "/" + suffix;
    return base + suffix;
  }

  global.CropMandiConfig = Object.assign({}, existing, {
    apiBaseUrl: base,
    apiUrl: apiUrl
  });
})(window);
