/* CropMandi multilingual voice assistant.
 * Input: browser MediaRecorder + local faster-whisper endpoint (no browser STT service).
 * Output: neural Edge TTS endpoint, with installed browser voices as a fallback.
 */
(function () {
  "use strict";

  const defaults = {
    endpoint: "http://127.0.0.1:8001/api/voice/command",
    selectors: {
      crop: "#cropFilter, #cropSelect, select[name='crop']",
      variety: "#varietyFilter, #varietySelect, select[name='variety']",
      state: "#stateFilter, #stateSelect, select[name='state']",
      district: "#districtFilter, #districtSelect, select[name='district']",
      market: "#apmcFilter, #marketFilter, #mandiFilter, select[name='market']",
      quantity: "#quantityFilter, input[name='quantity']"
    },
    autoSpeak: true,
    showTextFallback: true,
    title: "CropMandi Voice Assistant"
  };
  const config = Object.assign({}, defaults, window.CropMandiVoiceConfig || {});
  config.selectors = Object.assign({}, defaults.selectors, (window.CropMandiVoiceConfig || {}).selectors || {});

  if (document.getElementById("cropmandi-voice-root")) return;

  const root = document.createElement("div");
  root.id = "cropmandi-voice-root";
  root.innerHTML = `
    <button class="cm-voice-fab" id="cmVoiceFab" type="button" aria-label="Open voice assistant" title="Voice assistant">
      <span aria-hidden="true">🎙️</span>
    </button>
    <section class="cm-voice-panel" id="cmVoicePanel" aria-label="CropMandi Voice Assistant" hidden>
      <header class="cm-voice-header">
        <div><strong>${escapeHTML(config.title)}</strong><small id="cmVoiceStatus">Ready to help</small></div>
        <button class="cm-voice-close" id="cmVoiceClose" type="button" aria-label="Close assistant">×</button>
      </header>
      <div class="cm-voice-language-row">
        <label for="cmVoiceLanguage">Language</label>
        <select id="cmVoiceLanguage">
          <option value="auto">Auto / ಸ್ವಯಂ / स्वतः</option>
          <option value="hi-IN">हिन्दी</option>
          <option value="en-IN" selected>English</option>
          <option value="kn-IN">ಕನ್ನಡ</option>
        </select>
        <button id="cmVoiceClear" type="button" class="cm-voice-small-button">Clear</button>
      </div>
      <div class="cm-voice-messages" id="cmVoiceMessages" aria-live="polite">
        <div class="cm-voice-message assistant">Ask me about crop prices, a mandi, a date, cold storage, weather, or website sections.</div>
      </div>
      <form class="cm-voice-compose" id="cmVoiceForm">
        <input id="cmVoiceText" type="text" autocomplete="off" placeholder="Ask in Hindi, English, or Kannada…" aria-label="Type a question" />
        <button id="cmVoiceSend" type="submit" aria-label="Send question">➤</button>
      </form>
      <div class="cm-voice-actions">
        <button id="cmVoiceMic" type="button" class="cm-voice-mic"><span aria-hidden="true">🎤</span> Speak</button>
        <button id="cmVoiceMute" type="button" class="cm-voice-small-button" aria-pressed="false">Mute</button>
        <button id="cmVoiceReplay" type="button" class="cm-voice-small-button" disabled>Replay</button>
        <button id="cmVoiceStop" type="button" class="cm-voice-small-button" disabled>Stop audio</button>
      </div>
      <p class="cm-voice-hint">Speech input is transcribed locally after the model's first download. Natural Hindi/Kannada audio uses an online voice service; a device voice is used if available.</p>
    </section>`;
  document.body.appendChild(root);

  const find = (id) => root.querySelector("#" + id);
  const fab = find("cmVoiceFab"), panel = find("cmVoicePanel"), input = find("cmVoiceText");
  const messages = find("cmVoiceMessages"), status = find("cmVoiceStatus"), mic = find("cmVoiceMic");
  const languageSelect = find("cmVoiceLanguage"), stopButton = find("cmVoiceStop");
  const replayButton = find("cmVoiceReplay"), muteButton = find("cmVoiceMute");
  let conversation = {}, lastAnswer = null, muted = false, requestId = 0, speechId = 0;
  let recorder = null, stream = null, recording = false, permissionPending = false, micId = 0;
  let recordingTimer = null, audio = null, audioUrl = null, finishPlayback = null;
  let speechController = null, commandController = null, transcribeController = null;
  let lastSubmitted = "", pending = false;
  const contextKey = "cropmandi_voice_context_v3";
  let lastPageSnapshot = "";
  const knownPages = ["/index.html", "/cropmandi_ai_dashboard/code.html", "/cropmandi_ai_my_crops/code.html",
    "/cropmandi_ai_harvest_route/code.html", "/cropmandi_mandi_price_ai/code.html", "/cropmandi_ai_analytics/code.html",
    "/cropmandi_ai_settings/code.html", "/cropmandi_ai_farm_calendar/code.html", "/cropmandi_ai_alert_center/code.html"];

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
  }
  function localized(en, hi, kn, language) {
    const lang = language || (languageSelect.value === "auto" ? (lastAnswer && lastAnswer.language) || "en" : languageSelect.value);
    return String(lang).startsWith("kn") ? kn : String(lang).startsWith("hi") ? hi : en;
  }
  function ready() { status.textContent = localized("Ready to help", "मदद के लिए तैयार", "ಸಹಾಯಕ್ಕೆ ಸಿದ್ಧ"); }
  function addMessage(type, text) {
    const item = document.createElement("div"); item.className = "cm-voice-message " + type;
    item.textContent = text; messages.appendChild(item); messages.scrollTop = messages.scrollHeight;
    while (messages.children.length > 60) messages.firstElementChild.remove();
  }
  function localDateISO() {
    const d = new Date(), pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  }
  function apiEndpoint(action) { return config.endpoint.replace(/\/command\/?$/, "/" + action); }
  async function request(action, options, controller, timeout) {
    const timer = window.setTimeout(() => controller.abort(), timeout);
    try {
      const r = await fetch(apiEndpoint(action), {...options, signal: controller.signal});
      if (!r.ok) {
        const payload = await r.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : `Service returned ${r.status}`);
      }
      return options.audio ? await r.blob() : await r.json();
    } finally { window.clearTimeout(timer); }
  }
  function read(selector) {
    try {
      const el = document.querySelector(selector);
      const value = el && String(el.value || "").trim();
      return value && !/^(select|choose|all|none|loading|failed|--)/i.test(value) ? value : "";
    } catch (_) { return ""; }
  }
  function pageContext() {
    const result = {};
    const pages = {
      dashboard: {commodity:"#dash-crop", variety:"#dash-series", market:"#dash-location", quantity:"#dash-quantity"},
      mandi: {commodity:"#mpa-crop", market:"#mpa-market", forecast_date:"#mpa-date"},
      harvest: {commodity:"#commodity", variety:"#series", origin:"#origin", quantity:"#quantity", vehicle_id:"#vehicle_id"},
      analytics: {commodity:"#analytics-commodity, #commodity-select", variety:"#analytics-variety", market:"#analytics-location, #location-select"}
    };
    const path = window.location.pathname;
    const selectors = path.includes("harvest_route") ? pages.harvest : path.includes("mandi_price_ai") ? pages.mandi
      : path.includes("analytics") ? pages.analytics : path.includes("dashboard") ? pages.dashboard : {};
    Object.entries(selectors).forEach(([key, sel]) => { const v = read(sel); if (v) result[key] = v; });
    // Explicit host configuration stays supported without reading hidden crop-editor forms.
    Object.entries(config.selectors || {}).forEach(([key, sel]) => {
      if (!result[key === "crop" ? "commodity" : key]) {
        const v = read(sel); if (v) result[key === "crop" ? "commodity" : key] = v;
      }
    });
    if (result.variety && result.variety.startsWith("[")) {
      try {
        const pair = JSON.parse(result.variety);
        if (Array.isArray(pair) && pair.length === 2) { result.variety = String(pair[0]); result.grade = String(pair[1]); }
      } catch (_) {}
    }
    if (path.includes("harvest_route")) {
      result.quantity_unit = "kg";
      result.vehicle_mode = read("input[name='vehicle_mode']:checked") || (document.getElementById("mode_manual")?.checked ? "manual" : "auto");
      result.ownership = document.getElementById("ownership_owned")?.checked ? "owned" : "hired";
    } else if (path.includes("dashboard")) { result.quantity_unit = "quintal"; }
    return result;
  }
  function getContext() {
    const page = pageContext(), snapshot = JSON.stringify(page);
    const unchanged = snapshot === lastPageSnapshot;
    const context = unchanged && Object.keys(conversation).length ? {...conversation} : {...conversation, ...page};
    if (!unchanged && page.commodity && page.commodity !== conversation.commodity) {
      if (!page.variety) delete context.variety;
      if (!page.grade) delete context.grade;
      delete context.pending_intent; delete context.target_date;
    }
    lastPageSnapshot = snapshot;
    return {...context, page: window.location.pathname, client_date: localDateISO()};
  }
  function saveContext() {
    try { sessionStorage.setItem(contextKey, JSON.stringify({conversation, language:languageSelect.value, muted, at:Date.now()})); } catch (_) {}
  }
  try {
    const saved = JSON.parse(sessionStorage.getItem(contextKey) || "null");
    if (saved && Date.now() - saved.at < 30 * 60 * 1000) {
      conversation = saved.conversation || {}; muted = !!saved.muted;
      if (["auto", "en-IN", "hi-IN", "kn-IN"].includes(saved.language)) languageSelect.value = saved.language;
    }
  } catch (_) {}
  function syncMute() { muteButton.textContent = muted ? "Unmute" : "Mute"; muteButton.setAttribute("aria-pressed", String(muted)); }
  syncMute();

  function stopSpeaking() {
    speechId++;
    if (speechController) { speechController.abort(); speechController = null; }
    if (audio) { audio.pause(); audio = null; }
    if (finishPlayback) { const finish = finishPlayback; finishPlayback = null; finish(false); }
    if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    stopButton.disabled = true;
  }
  function browserSpeak(text, language, id) {
    if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance !== "function") return Promise.resolve(false);
    return new Promise(resolve => {
      const synth = window.speechSynthesis;
      let finished = false, started = false;
      const finish = ok => {
        if (finished) return; finished = true; window.clearTimeout(timer); window.clearTimeout(voiceTimer);
        synth.removeEventListener("voiceschanged", begin);
        if (finishPlayback === finish) finishPlayback = null;
        resolve(ok);
      };
      const begin = () => {
        if (finished || started || id !== speechId) return;
        const voices = synth.getVoices(), voice = voices.find(v => v.lang.toLowerCase().startsWith(language.slice(0,2)));
        if (!voice && !language.startsWith("en")) return;
        started = true;
        const utterance = new SpeechSynthesisUtterance(text); utterance.lang = language; utterance.rate = 0.92;
        if (voice) utterance.voice = voice;
        utterance.onend = () => finish(true); utterance.onerror = () => finish(false);
        synth.speak(utterance);
      };
      const timer = window.setTimeout(() => { synth.cancel(); finish(false); }, 60000);
      const voiceTimer = window.setTimeout(() => { begin(); if (!started) finish(false); }, 1200);
      finishPlayback = finish; synth.addEventListener("voiceschanged", begin); begin();
    });
  }
  async function speak(text, language) {
    stopSpeaking();
    if (muted || !config.autoSpeak || !text) return;
    const id = speechId, lang = String(language || "en").slice(0,2) + "-IN";
    stopButton.disabled = false;
    status.textContent = localized("Preparing voice…", "आवाज़ तैयार हो रही है…", "ಧ್ವನಿ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…");
    const controller = new AbortController(); speechController = controller;
    try {
      const blob = await request("speak", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text,language:lang}), audio:true}, controller, 15000);
      if (id !== speechId) return;
      if (!blob.size) throw new Error("Empty audio");
      audioUrl = URL.createObjectURL(blob); const player = new Audio(audioUrl); audio = player;
      status.textContent = localized("Speaking…", "बोल रहा हूँ…", "ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ…");
      const played = await new Promise(resolve => {
        const finish = ok => { window.clearTimeout(timer); player.onended = null; player.onerror = null; if (finishPlayback === finish) finishPlayback = null; resolve(ok); };
        const timer = window.setTimeout(() => { player.pause(); finish(false); }, 60000);
        finishPlayback = finish; player.onended = () => finish(true); player.onerror = () => finish(false);
        Promise.resolve(player.play()).catch(() => finish(false));
      });
      if (!played && id === speechId) throw new Error("Playback unavailable");
    } catch (_) {
      if (id !== speechId) return;
      if (audio) { audio.pause(); audio = null; }
      if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
      const played = await browserSpeak(text, lang, id);
      if (!played && id === speechId) addMessage("assistant", localized("Spoken audio is unavailable. The answer is displayed above.", "आवाज़ उपलब्ध नहीं है। जवाब ऊपर लिखा है।", "ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ. ಉತ್ತರವನ್ನು ಮೇಲೆ ತೋರಿಸಲಾಗಿದೆ."));
    } finally {
      if (id === speechId) { stopSpeaking(); ready(); }
    }
  }
  function announce(text, language) {
    const spokenLanguage = language || (languageSelect.value === "auto" ? (lastAnswer?.language || "en") : languageSelect.value);
    addMessage("assistant", text);
    lastAnswer = {text, language: spokenLanguage};
    replayButton.disabled = false;
    return speak(text, spokenLanguage);
  }
  function stopTracks() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; }
  function resetMic() { mic.classList.remove("is-listening"); mic.textContent = localized("🎤 Speak", "🎤 बोलें", "🎤 ಮಾತನಾಡಿ"); mic.disabled = permissionPending; }
  function stopListening(discard = true) {
    micId++; permissionPending = false; window.clearTimeout(recordingTimer);
    if (recorder && recorder.state !== "inactive") {
      recorder.discard = discard; recording = false;
      try { recorder.stop(); } catch (_) { stopTracks(); recorder = null; }
    } else { stopTracks(); recording = false; }
    resetMic();
  }
  function cancelRequests() {
    requestId++; pending = false;
    if (commandController) commandController.abort();
    if (transcribeController) transcribeController.abort();
    commandController = null; transcribeController = null;
  }
  async function transcribeRecording(blob, id) {
    const controller = new AbortController(); transcribeController = controller;
    status.textContent = localized("Transcribing locally…", "स्थानीय लिप्यंतरण…", "ಸ್ಥಳೀಯ ಲಿಪ್ಯಂತರಣ…");
    try {
      const form = new FormData(); const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
      form.append("audio", blob, "recording." + ext); form.append("language", languageSelect.value);
      const result = await request("transcribe", {method:"POST",body:form}, controller, 95000);
      if (id !== requestId) return;
      const data = result.data || {}, text = String(data.text || "").trim();
      if (!text) throw new Error(localized("No clear words detected. Please retry.", "स्पष्ट शब्द नहीं मिले। फिर बोलिए।", "ಸ್ಪಷ್ಟ ಪದಗಳು ಕೇಳಿಸಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."));
      if (languageSelect.value === "auto" && !["en","hi","kn"].includes(data.detected_language)) {
        addMessage("assistant", localized("Please choose English, Hindi or Kannada and retry.", "English, हिन्दी या ಕನ್ನಡ चुनकर फिर बोलिए।", "English, हिन्दी ಅಥವಾ ಕನ್ನಡ ಆಯ್ಕೆಮಾಡಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.")); return;
      }
      if (data.needs_confirmation || (languageSelect.value === "auto" && data.language_probability < 0.5)) {
        input.value = text;
        const reviewLanguage = ["en", "hi", "kn"].includes(data.detected_language) ? data.detected_language : "en";
        await announce(localized("Please check the transcript in the text box. Edit it or choose a language, then press Send.", "लिखे गए शब्द जाँचें। सुधारें या भाषा चुनें, फिर भेजें दबाएँ।", "ಪಠ್ಯ ಪೆಟ್ಟಿಗೆಯಲ್ಲಿನ ಲಿಪ್ಯಂತರಣ ಪರಿಶೀಲಿಸಿ. ಸರಿಪಡಿಸಿ ಅಥವಾ ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ, ನಂತರ ಕಳುಹಿಸಿ.", reviewLanguage), reviewLanguage);
        if (id === requestId) input.focus();
        return;
      }
      await submitText(text, languageSelect.value === "auto" ? data.detected_language + "-IN" : languageSelect.value);
    } catch (e) {
      if (id === requestId) { addMessage("assistant", e.name === "AbortError" ? localized("Transcription timed out. Retry a shorter clip.", "समय सीमा पूरी हुई। छोटा रिकॉर्डिंग भेजें।", "ಸಮಯ ಮೀರಿದೆ. ಚಿಕ್ಕ ಧ್ವನಿ ಕಳುಹಿಸಿ.") : e.message); ready(); }
    } finally { if (id === requestId) { transcribeController = null; ready(); } }
  }
  async function startRecording() {
    if (permissionPending || recording) return;
    stopListening(true); cancelRequests(); stopSpeaking();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder !== "function") {
      ready();
      announce(localized("Audio recording requires a supported browser on localhost or HTTPS. You can type your question.", "रिकॉर्डिंग के लिए localhost या HTTPS पर समर्थित ब्राउज़र चाहिए। प्रश्न लिख सकते हैं।", "ಧ್ವನಿ ದಾಖಲಿಸಲು localhost ಅಥವಾ HTTPS ನಲ್ಲಿ ಬೆಂಬಲಿತ ಬ್ರೌಸರ್ ಬೇಕು. ಪ್ರಶ್ನೆ ಬರೆಯಬಹುದು.")); return;
    }
    const token = ++micId; permissionPending = true; mic.disabled = true;
    status.textContent = localized("Waiting for microphone permission…", "माइक्रोफोन की अनुमति की प्रतीक्षा…", "ಮೈಕ್ರೋಫೋನ್ ಅನುಮತಿಗಾಗಿ ಕಾಯಲಾಗುತ್ತಿದೆ…");
    const permissionTimer = window.setTimeout(() => {
      if (token !== micId) return;
      micId++; permissionPending = false; resetMic(); ready();
      announce(localized("Microphone permission is still pending. Allow it in site settings and retry.", "माइक्रोफोन अनुमति लंबित है। साइट सेटिंग में अनुमति देकर फिर कोशिश करें।", "ಮೈಕ್ರೋಫೋನ್ ಅನುಮತಿ ಬಾಕಿಯಿದೆ. ಸೈಟ್ ಸೆಟ್ಟಿಂಗ್‌ನಲ್ಲಿ ಅನುಮತಿ ನೀಡಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."));
    }, 15000);
    try {
      const captured = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if (token !== micId) { captured.getTracks().forEach(t => t.stop()); return; }
      window.clearTimeout(permissionTimer); permissionPending = false; stream = captured;
      const mime = ["audio/webm;codecs=opus","audio/ogg;codecs=opus","audio/mp4"].find(m => MediaRecorder.isTypeSupported?.(m));
      const current = mime ? new MediaRecorder(stream,{mimeType:mime}) : new MediaRecorder(stream);
      recorder = current; const chunks = []; const id = requestId;
      current.ondataavailable = e => { if (e.data?.size) chunks.push(e.data); };
      current.onerror = () => { stopListening(true); announce(localized("Recording failed. Please retry.", "रिकॉर्डिंग विफल हुई। फिर कोशिश करें।", "ಧ್ವನಿ ದಾಖಲೆ ವಿಫಲವಾಯಿತು. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.")); ready(); };
      current.onstop = () => {
        window.clearTimeout(current.recordingTimer);
        const blob = new Blob(chunks,{type:current.mimeType || "audio/webm"});
        // Own the captured stream so an old recorder cannot stop a newer session.
        captured.getTracks().forEach(t => t.stop());
        if (recorder === current) { recorder = null; stream = null; recording = false; resetMic(); }
        if (!current.discard && id === requestId && blob.size) void transcribeRecording(blob,id);
      };
      current.start(250); recording = true; mic.disabled = false; mic.classList.add("is-listening");
      mic.textContent = localized("⏹ Finish & send", "⏹ समाप्त और भेजें", "⏹ ಮುಗಿಸಿ ಕಳುಹಿಸಿ");
      status.textContent = localized("Listening… (30 second limit)", "सुन रहा हूँ… (30 सेकंड सीमा)", "ಕೇಳುತ್ತಿದ್ದೇನೆ… (30 ಸೆಕೆಂಡ್ ಮಿತಿ)");
      recordingTimer = current.recordingTimer = window.setTimeout(() => stopListening(false), 30000);
    } catch (e) {
      if (token !== micId) return;
      stopTracks(); permissionPending = false; resetMic(); ready();
      announce(localized(e.name === "NotAllowedError" ? "Microphone permission denied. Allow it in browser site settings." : "Microphone unavailable. Check that it is connected and not busy.", "माइक्रोफोन उपलब्ध नहीं है। ब्राउज़र की अनुमति और कनेक्शन जाँचें।", "ಮೈಕ್ರೋಫೋನ್ ಲಭ್ಯವಿಲ್ಲ. ಬ್ರೌಸರ್ ಅನುಮತಿ ಮತ್ತು ಸಂಪರ್ಕ ಪರಿಶೀಲಿಸಿ."));
    } finally { window.clearTimeout(permissionTimer); }
  }
  async function navigate(action, id) {
    if (!action || id !== requestId) return;
    if (action.type === "back") {
      // history.length can include another site; only return to our tracked app page.
      let previous = null;
      try { previous = sessionStorage.getItem("cropmandi_voice_previous_page"); } catch (_) {}
      if (previous && knownPages.includes(previous.split("#")[0])) window.location.assign(previous);
      else addMessage("assistant", localized("No previous CropMandi page is available.", "पिछला CropMandi पेज उपलब्ध नहीं है।", "ಹಿಂದಿನ CropMandi ಪುಟ ಲಭ್ಯವಿಲ್ಲ."));
      return;
    }
    if (action.type !== "navigate" || !knownPages.includes(String(action.path || "").split("#")[0])) return;
    const destination = new URL(action.path, window.location.href);
    if (destination.origin !== window.location.origin) return;
    try {
      const response = await fetch(destination.pathname,{method:"HEAD",signal:AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error("Missing page");
      if (id === requestId) { saveContext(); window.location.assign(destination.pathname + destination.hash); }
    } catch (_) { if (id === requestId) addMessage("assistant", localized("That page is unavailable. Please retry.", "पेज उपलब्ध नहीं है। फिर कोशिश करें।", "ಪುಟ ಲಭ್ಯವಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.")); }
  }
  async function submitText(raw, language) {
    const text = String(raw || "").trim();
    if (!text || (pending && text === lastSubmitted)) return;
    stopListening(true); cancelRequests(); stopSpeaking();
    const id = requestId; pending = true; lastSubmitted = text; input.value = "";
    addMessage("user", text); status.textContent = localized("Processing…", "प्रक्रिया जारी है…", "ಪ್ರಕ್ರಿಯೆಯಲ್ಲಿದೆ…");
    commandController = new AbortController();
    try {
      const payload = await request("command", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,language:language || languageSelect.value,client_date:localDateISO(),context:getContext()})}, commandController, 45000);
      if (id !== requestId) return;
      if (!payload.success || !payload.data?.answer) throw new Error("Invalid service response");
      const data = payload.data; conversation = data.conversation || {}; saveContext();
      lastAnswer = {text:data.spoken_answer || data.answer,language:data.language || languageSelect.value}; replayButton.disabled = false;
      addMessage("assistant",data.answer);
      window.dispatchEvent(new CustomEvent("cropmandi:voice-response",{detail:data}));
      if (data.action?.type === "show_price") window.dispatchEvent(new CustomEvent("cropmandi:voice-action",{detail:data.action}));
      await speak(data.spoken_answer || data.answer,data.language);
      await navigate(data.action,id);
    } catch (e) {
      if (id === requestId) {
        const message = localized("The request failed or timed out. Please retry.", "अनुरोध विफल हुआ या समय सीमा पूरी हुई। फिर कोशिश करें।", "ವಿನಂತಿ ವಿಫಲವಾಯಿತು ಅಥವಾ ಸಮಯ ಮೀರಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.");
        addMessage("assistant",message); await speak(message,languageSelect.value === "auto" ? "en" : languageSelect.value);
      }
    } finally { if (id === requestId) { pending = false; commandController = null; ready(); if (!panel.hidden) input.focus(); } }
  }
  function openPanel() { panel.hidden = false; fab.classList.add("is-open"); fab.setAttribute("aria-expanded","true"); input.focus(); }
  function closePanel() { panel.hidden = true; fab.classList.remove("is-open"); fab.setAttribute("aria-expanded","false"); stopListening(); cancelRequests(); stopSpeaking(); ready(); }
  fab.addEventListener("click", () => panel.hidden ? openPanel() : closePanel());
  find("cmVoiceClose").addEventListener("click", closePanel);
  find("cmVoiceForm").addEventListener("submit", e => { e.preventDefault(); void submitText(input.value); });
  mic.addEventListener("click", () => recording ? stopListening(false) : void startRecording());
  stopButton.addEventListener("click", () => { stopSpeaking(); ready(); });
  replayButton.addEventListener("click", () => { if (lastAnswer && !recording) void speak(lastAnswer.text,lastAnswer.language); });
  muteButton.addEventListener("click", () => { muted = !muted; stopSpeaking(); syncMute(); saveContext(); ready(); });
  languageSelect.addEventListener("change", () => { stopListening(); cancelRequests(); stopSpeaking(); saveContext(); ready(); });
  find("cmVoiceClear").addEventListener("click", () => {
    stopListening(); cancelRequests(); stopSpeaking(); conversation = {}; lastAnswer = null; replayButton.disabled = true;
    messages.replaceChildren(); saveContext(); ready();
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) closePanel(); });
  window.addEventListener("pagehide", () => { saveContext(); stopListening(); cancelRequests(); stopSpeaking(); });
  try {
    const current = window.location.pathname + window.location.hash, last = sessionStorage.getItem("cropmandi_voice_current_page");
    if (last && last !== current) sessionStorage.setItem("cropmandi_voice_previous_page", last);
    sessionStorage.setItem("cropmandi_voice_current_page", current);
  } catch (_) {}
  window.CropMandiVoice = {open:openPanel,close:closePanel,send:submitText,stopListening,stopSpeaking,getContext,
    configure(options) { const selectors = {...config.selectors,...options?.selectors}; Object.assign(config,options || {}); config.selectors = selectors; }};
  if (!config.showTextFallback) find("cmVoiceForm").hidden = true;
})();
