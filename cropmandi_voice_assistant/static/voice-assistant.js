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
        <button id="cmVoiceStop" type="button" class="cm-voice-small-button" disabled>Stop audio</button>
      </div>
      <p class="cm-voice-hint">Speech input is transcribed locally after the model's first download. Natural Hindi/Kannada audio uses an online voice service; a device voice is used if available.</p>
    </section>`;
  document.body.appendChild(root);

  const fab = root.querySelector("#cmVoiceFab");
  const panel = root.querySelector("#cmVoicePanel");
  const closeButton = root.querySelector("#cmVoiceClose");
  const languageSelect = root.querySelector("#cmVoiceLanguage");
  const messages = root.querySelector("#cmVoiceMessages");
  const input = root.querySelector("#cmVoiceText");
  const form = root.querySelector("#cmVoiceForm");
  const sendButton = root.querySelector("#cmVoiceSend");
  const micButton = root.querySelector("#cmVoiceMic");
  const stopButton = root.querySelector("#cmVoiceStop");
  const status = root.querySelector("#cmVoiceStatus");
  const clearButton = root.querySelector("#cmVoiceClear");

  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let listening = false;
  let discardRecording = false;
  let transcriptionInFlight = false;
  let requestInFlight = false;
  let playingAudio = null;
  let playingObjectUrl = null;

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }

  function localDateISO() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  function apiEndpoint(action) {
    if (action === "command") return config.endpoint;
    try {
      const url = new URL(config.endpoint, window.location.href);
      if (/\/command\/?$/.test(url.pathname)) {
        url.pathname = url.pathname.replace(/\/command\/?$/, `/${action}`);
      } else {
        url.pathname = url.pathname.replace(/\/$/, "") + `/${action}`;
      }
      return url.toString();
    } catch (_) {
      return config.endpoint.replace(/\/command\/?$/, `/${action}`);
    }
  }

  function readSelectedValue(selector) {
    if (!selector) return "";
    let element = null;
    try { element = document.querySelector(selector); } catch (_) { return ""; }
    if (!element) return "";
    const value = String(element.value || "").trim();
    if (!value || /^(select|choose|all|none|--)/i.test(value)) return "";
    return value;
  }

  function getContext() {
    const context = { client_date: localDateISO(), page: window.location.pathname };
    Object.keys(config.selectors).forEach((key) => {
      const value = readSelectedValue(config.selectors[key]);
      if (value) context[key] = value;
    });
    if (context.crop) context.commodity = context.crop.toLowerCase();
    return context;
  }

  function setStatus(text) { status.textContent = text; }

  function addMessage(type, text) {
    const item = document.createElement("div");
    item.className = `cm-voice-message ${type}`;
    item.textContent = text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  }

  function openPanel() {
    panel.hidden = false;
    fab.classList.add("is-open");
    fab.setAttribute("aria-expanded", "true");
    input.focus();
  }

  function closePanel() {
    panel.hidden = true;
    fab.classList.remove("is-open");
    fab.setAttribute("aria-expanded", "false");
    stopListening(true);
    stopSpeaking();
  }

  function normalizedLanguage(language) {
    const value = String(language || languageSelect.value || "en-IN").toLowerCase();
    if (value.startsWith("hi")) return "hi-IN";
    if (value.startsWith("kn")) return "kn-IN";
    return "en-IN";
  }

  function getBrowserVoices() {
    if (!("speechSynthesis" in window)) return Promise.resolve([]);
    const synth = window.speechSynthesis;
    const first = synth.getVoices() || [];
    if (first.length) return Promise.resolve(first);
    return new Promise((resolve) => {
      let complete = false;
      const finish = () => {
        if (complete) return;
        complete = true;
        try { synth.removeEventListener("voiceschanged", finish); } catch (_) {}
        resolve(synth.getVoices() || []);
      };
      try { synth.addEventListener("voiceschanged", finish, { once: true }); } catch (_) {}
      window.setTimeout(finish, 1200);
    });
  }

  async function speakWithBrowser(text, language) {
    if (!("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance !== "function") return false;
    const requestedLanguage = normalizedLanguage(language);
    const voices = await getBrowserVoices();
    const shortLanguage = requestedLanguage.slice(0, 2).toLowerCase();
    const voice = voices.find((candidate) => String(candidate.lang || "").toLowerCase() === requestedLanguage.toLowerCase())
      || voices.find((candidate) => String(candidate.lang || "").toLowerCase().startsWith(shortLanguage + "-"));
    // Avoid reading Kannada/Hindi text through an unrelated English voice.
    if (!voice && shortLanguage !== "en") return false;

    return new Promise((resolve) => {
      try {
        const utterance = new SpeechSynthesisUtterance(String(text || ""));
        utterance.lang = requestedLanguage;
        utterance.rate = 0.92;
        utterance.pitch = 1;
        if (voice) utterance.voice = voice;
        let finished = false;
        const done = (result) => {
          if (finished) return;
          finished = true;
          window.clearTimeout(timer);
          resolve(result);
        };
        utterance.onend = () => done(true);
        utterance.onerror = () => done(false);
        const timer = window.setTimeout(() => done(false), Math.max(7000, String(text).length * 180));
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      } catch (_) { resolve(false); }
    });
  }

  async function speak(text, language) {
    if (!config.autoSpeak || !String(text || "").trim()) return;
    stopSpeaking();
    const selectedLanguage = normalizedLanguage(language);
    stopButton.disabled = false;
    setStatus("Preparing voice…");

    // Prefer the neural Indian-language voice so Hindi and Kannada do not depend
    // on which Windows/browser language packs happen to be installed.
    try {
      const response = await fetch(apiEndpoint("speak"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "audio/mpeg" },
        body: JSON.stringify({ text: String(text), language: selectedLanguage })
      });
      if (!response.ok) throw new Error(`TTS endpoint returned ${response.status}`);
      const blob = await response.blob();
      if (!blob.size) throw new Error("Empty audio response");
      playingObjectUrl = URL.createObjectURL(blob);
      const audio = new Audio(playingObjectUrl);
      playingAudio = audio;
      setStatus("Speaking…");
      await new Promise((resolve, reject) => {
        let done = false;
        const finish = (error) => {
          if (done) return;
          done = true;
          audio.onended = null;
          audio.onerror = null;
          error ? reject(error) : resolve();
        };
        audio.onended = () => finish();
        audio.onerror = () => finish(new Error("Audio playback failed"));
        Promise.resolve(audio.play()).catch((error) => finish(error));
      });
      stopSpeaking();
      setStatus("Ready to help");
      return;
    } catch (_) {
      // If online neural TTS is unavailable, try an installed on-device voice.
      stopSpeaking();
    }

    const browserPlayed = await speakWithBrowser(text, selectedLanguage);
    if (!browserPlayed) {
      const unavailable = {
        "hi-IN": "हिंदी में आवाज़ उपलब्ध नहीं है। इंटरनेट से जुड़ें या अपने डिवाइस में हिंदी की आवाज़ स्थापित करें।",
        "kn-IN": "ಕನ್ನಡ ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ. ಇಂಟರ್ನೆಟ್ ಸಂಪರ್ಕಿಸಿ ಅಥವಾ ಸಾಧನದಲ್ಲಿ ಕನ್ನಡ ಧ್ವನಿಯನ್ನು ಸ್ಥಾಪಿಸಿ.",
        "en-IN": "Audio playback is unavailable. Check the connection or use the text answer above."
      };
      addMessage("assistant", unavailable[selectedLanguage]);
    }
    stopButton.disabled = true;
    setStatus("Ready to help");
  }

  function stopSpeaking() {
    if (playingAudio) {
      try { playingAudio.pause(); playingAudio.currentTime = 0; } catch (_) {}
      playingAudio = null;
    }
    if (playingObjectUrl) {
      try { URL.revokeObjectURL(playingObjectUrl); } catch (_) {}
      playingObjectUrl = null;
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    stopButton.disabled = true;
  }

  function resetMicButton() {
    micButton.classList.remove("is-listening");
    micButton.innerHTML = "<span aria-hidden=\"true\">🎤</span> Speak";
    micButton.disabled = transcriptionInFlight || requestInFlight;
  }

  function stopTracks() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => { try { track.stop(); } catch (_) {} });
      mediaStream = null;
    }
  }

  function stopListening(discard) {
    const activeRecorder = mediaRecorder && mediaRecorder.state !== "inactive";
    if (activeRecorder) {
      discardRecording = discard !== false;
      listening = false;
      try {
        // Do not stop microphone tracks yet. MediaRecorder must first emit its
        // final dataavailable event and then onstop; stopping tracks too early
        // can truncate the WebM/Opus container and make Whisper return HTTP 422.
        mediaRecorder.stop();
      } catch (error) {
        stopTracks();
        mediaRecorder = null;
        audioChunks = [];
      }
    } else {
      listening = false;
      stopTracks();
    }
    resetMicButton();
    if (status.textContent === "Recording…") setStatus("Ready to help");
  }

  async function transcribeRecording(blob) {
    if (!blob || !blob.size) {
      addMessage("assistant", "I didn't receive an audio recording. Please try again.");
      setStatus("Ready to help");
      return;
    }
    transcriptionInFlight = true;
    resetMicButton();
    setStatus("Transcribing speech locally…");
    try {
      const body = new FormData();
      const extension = blob.type && blob.type.includes("mp4") ? "m4a" : blob.type && blob.type.includes("ogg") ? "ogg" : "webm";
      body.append("audio", blob, `cropmandi-recording.${extension}`);
      body.append("language", languageSelect.value);
      const response = await fetch(apiEndpoint("transcribe"), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) {
        throw new Error(payload.detail || payload.error || `Speech service returned ${response.status}`);
      }
      const transcript = String((payload.data && payload.data.text) || payload.text || "").trim();
      if (!transcript) {
        addMessage("assistant", languageSelect.value === "hi-IN"
          ? "मैं आपकी बात नहीं सुन पाया। कृपया थोड़ा पास से और साफ़ बोलकर फिर कोशिश करें।"
          : languageSelect.value === "kn-IN"
            ? "ನಿಮ್ಮ ಮಾತು ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಹತ್ತಿರದಿಂದ ಸ್ಪಷ್ಟವಾಗಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."
            : "I couldn't hear clear words. Please speak a little closer to the microphone and try again.");
        setStatus("Ready to help");
        return;
      }
      input.value = transcript;
      await submitText(transcript);
    } catch (error) {
      const message = String(error && error.message ? error.message : error);
      addMessage("assistant", `Voice input failed: ${message}`);
      setStatus("Voice input unavailable");
    } finally {
      transcriptionInFlight = false;
      resetMicButton();
      if (!requestInFlight && status.textContent !== "Connection problem") setStatus("Ready to help");
    }
  }

  async function startRecording() {
    if (requestInFlight || transcriptionInFlight) return;
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function" || typeof window.MediaRecorder !== "function") {
      addMessage("assistant", "This browser cannot record audio. Use the text box, or open CropMandi in a recent Chrome or Edge browser on localhost.");
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const preferredMime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
        .find((mime) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(mime));
      mediaRecorder = preferredMime ? new MediaRecorder(mediaStream, { mimeType: preferredMime }) : new MediaRecorder(mediaStream);
      audioChunks = [];
      discardRecording = false;
      mediaRecorder.ondataavailable = (event) => { if (event.data && event.data.size) audioChunks.push(event.data); };
      mediaRecorder.onerror = () => {
        addMessage("assistant", "The browser could not record this clip. Please check microphone permissions and retry.");
        stopListening(true);
      };
      mediaRecorder.onstop = () => {
        const recorder = mediaRecorder;
        const discarded = discardRecording;
        const blob = new Blob(audioChunks, { type: (recorder && recorder.mimeType) || "audio/webm" });
        audioChunks = [];
        mediaRecorder = null;
        listening = false;
        stopTracks();
        resetMicButton();
        if (!discarded && blob.size) void transcribeRecording(blob);
      };
      // Periodic chunks make recording more reliable across browsers; the final
      // onstop event still flushes the last chunk before we upload the blob.
      mediaRecorder.start(250);
      listening = true;
      micButton.classList.add("is-listening");
      micButton.innerHTML = "<span aria-hidden=\"true\">⏹</span> Finish &amp; send";
      micButton.disabled = false;
      setStatus("Recording…");
      addMessage("assistant", languageSelect.value === "hi-IN"
        ? "अब बोलिए। पूरा होने पर ‘Finish & send’ दबाएँ।"
        : languageSelect.value === "kn-IN"
          ? "ಈಗ ಮಾತನಾಡಿ. ಮುಗಿದಾಗ ‘Finish & send’ ಒತ್ತಿ."
          : "Speak now. Press ‘Finish & send’ when you're done.");
    } catch (error) {
      stopTracks();
      listening = false;
      resetMicButton();
      const message = error && error.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access in your browser's site settings."
        : "Could not access the microphone. Check that it is connected and not being used by another app.";
      addMessage("assistant", message);
      setStatus("Microphone unavailable");
    }
  }

  async function submitText(rawText) {
    const text = String(rawText || "").trim();
    if (!text || requestInFlight) return;
    requestInFlight = true;
    sendButton.disabled = true;
    micButton.disabled = true;
    input.value = "";
    addMessage("user", text);
    setStatus("Thinking…");
    stopListening(true);

    try {
      const response = await fetch(apiEndpoint("command"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ text, language: languageSelect.value, client_date: localDateISO(), context: getContext() })
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) throw new Error(payload.error || payload.detail || `Request failed (${response.status})`);
      const data = payload.data || {};
      const answer = data.answer || "I couldn't prepare an answer for that request.";
      addMessage("assistant", answer);
      setStatus("Ready to help");
      window.dispatchEvent(new CustomEvent("cropmandi:voice-response", { detail: data }));
      if (data.action && data.action.type === "show_price") {
        window.dispatchEvent(new CustomEvent("cropmandi:voice-action", { detail: data.action }));
      }
      await speak(answer, data.language || languageSelect.value);
      if (data.action && data.action.type === "navigate" && data.action.path) {
        window.location.assign(data.action.path);
      }
    } catch (error) {
      const message = String(error && error.message ? error.message : error);
      addMessage("assistant", `Sorry, I couldn't connect to CropMandi. ${message}`);
      setStatus("Connection problem");
    } finally {
      requestInFlight = false;
      sendButton.disabled = false;
      micButton.disabled = transcriptionInFlight;
      input.focus();
    }
  }

  fab.addEventListener("click", () => panel.hidden ? openPanel() : closePanel());
  closeButton.addEventListener("click", closePanel);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitText(input.value);
  });
  micButton.addEventListener("click", () => {
    if (listening) stopListening(false);
    else void startRecording();
  });
  stopButton.addEventListener("click", stopSpeaking);
  languageSelect.addEventListener("change", () => {
    const placeholders = { "en-IN": "Ask in English…", "hi-IN": "हिंदी में पूछें…", "kn-IN": "ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ…" };
    input.placeholder = placeholders[languageSelect.value] || "Ask a question…";
    if (listening) stopListening(true);
    stopSpeaking();
  });
  clearButton.addEventListener("click", () => {
    messages.innerHTML = "";
    stopSpeaking();
    addMessage("assistant", languageSelect.value === "hi-IN"
      ? "मैं आपकी फसल के भाव, मंडी, तारीख, कोल्ड स्टोरेज, मौसम और वेबसाइट नेविगेशन में मदद कर सकता हूँ।"
      : languageSelect.value === "kn-IN"
        ? "ಬೆಳೆ ಬೆಲೆ, ಮಾರುಕಟ್ಟೆ, ದಿನಾಂಕ, ಶೀತಗೃಹ, ಹವಾಮಾನ ಮತ್ತು ವೆಬ್‌ಸೈಟ್ ನ್ಯಾವಿಗೇಶನ್‌ನಲ್ಲಿ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
        : "I can help with crop prices, mandis, dates, cold storage, weather, and website navigation.");
  });

  window.CropMandiVoice = {
    open: openPanel,
    close: closePanel,
    send: submitText,
    stopListening: stopListening,
    stopSpeaking: stopSpeaking,
    getContext: getContext,
    configure: function (options) {
      Object.assign(config, options || {});
      config.selectors = Object.assign({}, config.selectors, (options || {}).selectors || {});
    }
  };

  if (!config.showTextFallback) form.hidden = true;
})();
