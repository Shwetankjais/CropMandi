/**
 * Razorpay TEST checkout — server-priced ₹100 demo.
 * Supports both official Razorpay Checkout and an interactive Test Sandbox modal.
 */
(function () {
  "use strict";

  var DEMO_AMOUNT_INR = 100;
  var CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";
  var paying = false;

  function api() {
    return window.CropMandiAPI;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function userMessage(err) {
    var code = err && err.code;
    var status = err && err.status;
    if (code === "invalid_signature" || code === "invalid_order") {
      return "Payment verification failed.";
    }
    if (code === "invalid_amount" || code === "invalid_currency" || code === "invalid_crop") {
      return "Unable to create payment order.";
    }
    if (code === "payment_failed") {
      return "Payment failed. Please try again.";
    }
    if (status === 0 || (err && err.name === "TypeError")) {
      return "Network error. Please verify backend is running on port 8001.";
    }
    return (err && err.message) || "Something went wrong. Please try again.";
  }

  function setStatus(text) {
    var s = el("dash-pay-status");
    var e = el("dash-pay-error");
    var ok = el("dash-pay-success");
    if (s) {
      s.textContent = text || "";
      s.classList.toggle("hidden", !text);
    }
    if (e) {
      e.textContent = "";
      e.classList.add("hidden");
    }
    if (ok) {
      ok.textContent = "";
      ok.classList.add("hidden");
    }
  }

  function setBusy(busy) {
    var btn = el("dash-pay-button");
    paying = !!busy;
    if (!btn) {
      return;
    }
    btn.disabled = !!busy;
    btn.textContent = busy ? "Processing…" : "Pay ₹100 (Test Mode)";
  }

  function setError(text) {
    var s = el("dash-pay-status");
    var e = el("dash-pay-error");
    var ok = el("dash-pay-success");
    if (s) {
      s.textContent = "";
      s.classList.add("hidden");
    }
    if (ok) {
      ok.textContent = "";
      ok.classList.add("hidden");
    }
    if (e) {
      e.textContent = text || "Payment failed. Please try again.";
      e.classList.remove("hidden");
    }
    setBusy(false);
  }

  function setSuccess(text) {
    var s = el("dash-pay-status");
    var e = el("dash-pay-error");
    var ok = el("dash-pay-success");
    if (s) {
      s.textContent = "";
      s.classList.add("hidden");
    }
    if (e) {
      e.textContent = "";
      e.classList.add("hidden");
    }
    if (ok) {
      ok.innerHTML = text || "";
      ok.classList.toggle("hidden", !text);
    }
    setBusy(false);
  }

  function cropQty() {
    var cropEl = el("dash-storage-crop");
    var qtyEl = el("dash-storage-qty");
    var crop = cropEl && cropEl.value ? cropEl.value : "coffee";
    var raw = qtyEl ? String(qtyEl.value || "").trim() : "";
    var qty = Number(raw);
    if (!raw || !Number.isFinite(qty) || qty <= 0) {
      qty = 10;
    }
    return { crop: crop, quantity: qty };
  }

  function loadCheckoutScript() {
    return new Promise(function (resolve) {
      if (typeof window.Razorpay === "function") {
        resolve(true);
        return;
      }
      var existing = document.querySelector('script[src="' + CHECKOUT_SCRIPT + '"]');
      if (existing) {
        existing.addEventListener("load", function () {
          resolve(typeof window.Razorpay === "function");
        });
        existing.addEventListener("error", function () {
          resolve(false);
        });
        return;
      }
      var script = document.createElement("script");
      script.src = CHECKOUT_SCRIPT;
      script.async = true;
      script.onload = function () {
        resolve(typeof window.Razorpay === "function");
      };
      script.onerror = function () {
        resolve(false);
      };
      document.head.appendChild(script);
    });
  }

  function verifyOrder(order, rzpResponse) {
    var client = api();
    if (!client) {
      setError("Something went wrong. Please try again.");
      return;
    }
    setStatus("Verifying payment signature with backend...");
    return client
      .verifyPayment({
        razorpay_order_id: order.order_id,
        razorpay_payment_id: rzpResponse.razorpay_payment_id,
        razorpay_signature: rzpResponse.razorpay_signature,
      })
      .then(function (body) {
        if (!body || body.verified !== true) {
          throw new Error("Payment verification failed.");
        }
        var status = body.payment && body.payment.status;
        var payId = rzpResponse.razorpay_payment_id;
        setSuccess(
          '<div class="p-3 bg-primary-fixed/20 border border-primary/30 rounded-xl mt-3 text-left">' +
            '<div class="flex items-center gap-2 text-primary font-bold text-sm mb-1">' +
              '<span class="material-symbols-outlined text-base">check_circle</span>' +
              '<span>Payment Successful (Test Mode)</span>' +
            '</div>' +
            '<p class="text-xs text-on-surface-variant">Order: <code class="font-mono text-primary font-bold">' + order.order_id + '</code> · Payment ID: <code class="font-mono">' + payId + '</code></p>' +
            '<p class="text-xs text-on-surface-variant mt-1">Crop: <strong class="capitalize">' + order.crop + '</strong> (' + order.quantity + ' kg) · Amount Paid: <strong>₹' + DEMO_AMOUNT_INR + '</strong> · Status: <span class="text-xs px-2 py-0.5 rounded-full bg-primary text-white font-bold">' + status + '</span></p>' +
          '</div>'
        );
      })
      .catch(function (err) {
        setError(userMessage(err));
      });
  }

  /* Interactive Sandbox Checkout Modal */
  function openSandboxModal(order) {
    var modalId = "cropmandi-payment-sandbox-modal";
    var old = document.getElementById(modalId);
    if (old) old.remove();

    var overlay = document.createElement("div");
    overlay.id = modalId;
    overlay.className = "fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4";
    
    overlay.innerHTML =
      '<div class="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-outline-variant/30 text-on-surface animate-fade-in">' +
        '<!-- Header -->' +
        '<div class="bg-[#004532] text-white p-5 flex justify-between items-center">' +
          '<div class="flex items-center gap-3">' +
            '<div class="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center text-white font-bold">' +
              '<span class="material-symbols-outlined text-lg">shield</span>' +
            '</div>' +
            '<div>' +
              '<h3 class="font-bold text-base leading-tight">Razorpay Test Checkout</h3>' +
              '<p class="text-xs text-primary-fixed-dim">CropMandi AI · Demo Payment</p>' +
            '</div>' +
          '</div>' +
          '<button id="sb-close-btn" type="button" class="text-white/70 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors">' +
            '<span class="material-symbols-outlined text-xl">close</span>' +
          '</button>' +
        '</div>' +
        '<!-- Order Amount Summary -->' +
        '<div class="bg-surface-container-low p-4 border-b border-outline-variant/20 flex justify-between items-center">' +
          '<div>' +
            '<span class="text-xs text-on-surface-variant block uppercase font-bold tracking-wider">Payable Amount</span>' +
            '<span class="text-xs text-on-surface-variant capitalize">' + order.crop + ' · ' + order.quantity + ' kg demo slot</span>' +
          '</div>' +
          '<div class="text-2xl font-bold text-primary">₹' + DEMO_AMOUNT_INR + '.00</div>' +
        '</div>' +
        '<!-- Payment Methods -->' +
        '<div class="p-5 space-y-4">' +
          '<div class="flex gap-2 border-b border-outline-variant/20 pb-2 text-xs font-bold">' +
            '<button type="button" class="px-3 py-1.5 rounded-lg bg-primary text-white" id="sb-tab-card">💳 Card</button>' +
            '<button type="button" class="px-3 py-1.5 rounded-lg bg-surface-container text-on-surface-variant hover:text-primary" id="sb-tab-upi">📱 UPI / QR</button>' +
            '<button type="button" class="px-3 py-1.5 rounded-lg bg-surface-container text-on-surface-variant hover:text-primary" id="sb-tab-netbanking">🏦 Netbanking</button>' +
          '</div>' +
          '<div id="sb-view-card" class="space-y-3">' +
            '<div>' +
              '<label class="block text-xs font-bold text-on-surface-variant mb-1">Card Number (Test Cards Allowed)</label>' +
              '<div class="relative">' +
                '<input type="text" class="w-full p-2.5 pl-3 border border-outline-variant rounded-xl text-sm font-mono focus:border-primary focus:ring-1 focus:ring-primary outline-none" value="4111 2222 3333 4444" readonly/>' +
                '<span class="absolute right-3 top-2.5 text-xs font-bold text-primary bg-primary-fixed/20 px-2 py-0.5 rounded">TEST VISA</span>' +
              '</div>' +
            '</div>' +
            '<div class="grid grid-cols-2 gap-3">' +
              '<div>' +
                '<label class="block text-xs font-bold text-on-surface-variant mb-1">Expiry Date</label>' +
                '<input type="text" class="w-full p-2.5 border border-outline-variant rounded-xl text-sm font-mono" value="12/28" readonly/>' +
              '</div>' +
              '<div>' +
                '<label class="block text-xs font-bold text-on-surface-variant mb-1">CVV</label>' +
                '<input type="password" class="w-full p-2.5 border border-outline-variant rounded-xl text-sm font-mono" value="123" readonly/>' +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-start gap-2">' +
            '<span class="material-symbols-outlined text-base text-amber-700 shrink-0 mt-0.5">info</span>' +
            '<span>Test Mode Sandbox: No real money is charged. Click below to simulate instant authorized capture.</span>' +
          '</div>' +
        '</div>' +
        '<!-- Actions -->' +
        '<div class="p-5 border-t border-outline-variant/20 bg-surface-container-low flex justify-between items-center">' +
          '<button id="sb-cancel-btn" type="button" class="text-xs font-bold text-on-surface-variant hover:text-error transition-colors">Cancel</button>' +
          '<button id="sb-submit-btn" type="button" class="px-6 py-2.5 bg-primary text-white rounded-xl text-sm font-bold shadow-md hover:bg-primary-light active:scale-98 transition-all flex items-center gap-2">' +
            '<span class="material-symbols-outlined text-base">lock</span>' +
            '<span>Complete Test Payment</span>' +
          '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    function closeSandbox() {
      overlay.remove();
      setBusy(false);
      setStatus("Payment dismissed.");
    }

    overlay.querySelector("#sb-close-btn").addEventListener("click", closeSandbox);
    overlay.querySelector("#sb-cancel-btn").addEventListener("click", closeSandbox);

    overlay.querySelector("#sb-submit-btn").addEventListener("click", function () {
      var submitBtn = overlay.querySelector("#sb-submit-btn");
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-base">progress_activity</span> Processing…';

      setTimeout(function () {
        overlay.remove();
        var simulatedPaymentId = "pay_test_" + Math.random().toString(36).substring(2, 12);
        verifyOrder(order, {
          razorpay_order_id: order.order_id,
          razorpay_payment_id: simulatedPaymentId,
          razorpay_signature: "sandbox_signature",
        });
      }, 700);
    });
  }

  async function onPayClick(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (paying) {
      return;
    }
    var client = api();
    if (!client) {
      setError("Something went wrong. Please try again.");
      return;
    }
    try {
      setBusy(true);
      var sel = cropQty();
      setStatus("Creating payment order on server...");
      
      var data = await client.createPaymentOrder({
        crop: sel.crop,
        quantity: sel.quantity,
        amount: DEMO_AMOUNT_INR,
        currency: "INR",
        listing_id: "",
      });

      var keyId = String((data && data.key_id) || "").trim();
      var orderId = String((data && data.order_id) || "").trim();
      var amount = Number(data && data.amount);
      var currency = String((data && data.currency) || "INR").trim();

      if (!keyId || !orderId || !Number.isFinite(amount) || amount <= 0 || !currency) {
        throw Object.assign(new Error("Unable to create payment order."), {
          code: "razorpay_order_failed",
        });
      }

      var order = {
        key_id: keyId,
        order_id: orderId,
        amount: amount,
        currency: currency,
        crop: sel.crop,
        quantity: sel.quantity,
      };

      // Check if real live Razorpay key is configured
      var isSandbox = keyId.indexOf("sandbox") !== -1 || keyId.indexOf("demo") !== -1;
      var hasRzpScript = await loadCheckoutScript();

      if (!isSandbox && hasRzpScript && typeof window.Razorpay === "function") {
        setStatus("Opening Razorpay Checkout...");
        var checkout = new window.Razorpay({
          key: order.key_id,
          amount: order.amount,
          currency: order.currency,
          order_id: order.order_id,
          name: "CropMandi AI",
          description: "CropMandi AI Agriculture Payment",
          prefill: {},
          theme: { color: "#004532" },
          handler: function (rzpResponse) {
            verifyOrder(order, rzpResponse);
          },
          modal: {
            ondismiss: function () {
              client.cancelPayment(order.order_id).catch(function () {});
              setBusy(false);
              setStatus("Payment cancelled.");
            },
          },
        });
        if (checkout && typeof checkout.on === "function") {
          checkout.on("payment.failed", function () {
            setError("Payment failed. Please try again.");
          });
        }
        checkout.open();
      } else {
        // Launch polished Test Sandbox Checkout Modal
        setStatus("");
        openSandboxModal(order);
      }
    } catch (err) {
      setError(userMessage(err));
    }
  }

  function bindPayButton() {
    var btn = el("dash-pay-button");
    if (!btn) {
      return false;
    }
    if (btn.getAttribute("data-cropmandi-pay-bound") === "1") {
      return true;
    }
    btn.removeAttribute("onclick");
    btn.onclick = null;
    btn.addEventListener("click", onPayClick);
    btn.setAttribute("data-cropmandi-pay-bound", "1");
    return true;
  }

  function start() {
    bindPayButton();
  }

  start();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  }
})();
