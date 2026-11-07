# Multilingual Voice Assistant retest and fixes — 7 November 2026

Tested only the enhanced duplicate at http://127.0.0.1:8766. The original port-8001 processes (26062 and 33906) were not stopped or restarted. Only the duplicate was restarted to load fixes (current PID 46208). Its database is read-only.

## Results by test layer

- **34 live text/API assertions passed**, including all supplied navigation, historical prices, prediction/follow-up sequences, today's unavailable price, invalid dates and coffee-variety clarification. These used actual duplicate records and the existing prediction service.
- **Browser navigation and back navigation passed in English, Hindi and Kannada** between HarvestRoute and Mandi Price AI. The actual widget also showed genuine historical-price and forecast follow-ups in all three languages.
- **303 Python tests passed** (208 existing project tests + 95 voice tests), plus **15 widget lifecycle tests**. Full-suite writes used a populated disposable database copy, removed afterward.
- **9 real price/forecast spoken responses** (historical/tomorrow/next-week in each language) returned playable MP3 audio; PyAV decoded positive audio durations of about 16–27 seconds. User approval for sending these test-answer texts to Edge TTS was received after automatic approval review requested explicit consent.
- Actual browser audio entered Speaking state in all three languages; Stop restored Ready. Kannada Replay and Stop were verified as well. This verifies playback operation, not a human rating of accent/naturalness.
- Input speech tests used the same 12 generic synthesized clips before and after fixes, with local Whisper recognition. They were not physical microphone recordings.

| Input language | Navigation | Historical price | Tomorrow forecast | Next-week follow-up |
| --- | --- | --- | --- | --- |
| English | Pass | Pass | Pass | Pass |
| Hindi | Pass | Pass | Pass | Pass |
| Kannada | Pass | Review required | Pass | Pass |

**11/12 recorded input cases ran automatically with correct outcomes.** The remaining Kannada historical-date clip contained a corrupted/mixed-script year and market/crop words. It was flagged for review and was not automatically executed. This is an unresolved speech-recognition limitation, not a passing historical voice-input test. Kannada typed historical input and its spoken answer both worked. Human accents, field noise and physical microphone capture still need acceptance testing.

Verified data: Kolar tomato on 15 October 2026 was INR 800/quintal; the follow-up on 20 October returned INR 1,000/quintal. The existing model returned INR 1,310.73/quintal for 8 November and INR 1,311/quintal for 14 November, retaining the 26 October input date and experimental forecast labels. Bare Hindi kal still asks for clarification; explicit future phrasing now resolves tomorrow correctly.

## Issues fixed

1. English/Hindi speech distorted Mandi Price AI into Mundi Price and मंदी प्राइस. Added narrowly scoped page aliases, plus observed short Kannada page-name variants. The same variants inside ordinary price questions do not trigger navigation.
2. Added existing application names to the recognition vocabulary. Supported repetition controls stopped the repeated syllables/phrases observed in Kannada; the model remains local faster-whisper large-v3-turbo.
3. Corrected only impossible Kannada vowel-sign/virama ordering, preserving valid conjuncts and numerals. Added observed tomato-name variants; no numeric price/date guesses are made.
4. Added standard Kannada/Hindi spoken calendar-number parsing. Damaged spoken years, unresolved month dates and unsupported relative forecast targets now request a full date instead of using the current year, latest price or tomorrow.
5. Explicit Hindi कल होने वाले resolves as future; the observed अगले सप्ता variant resolves as next week. Ambiguous bare कल still requires clarification.
6. Transcript-review prompts are now spoken in the detected supported language and can be replayed. Suspicious transcripts stay editable and cannot automatically trigger a query/navigation.

The full free large-v3 model and built-in translation decoding were benchmarked on the same Kannada clips. They remained error-prone and were slower (roughly 18–47 seconds for full-model native decoding), so neither was enabled. The newly downloaded rejected full-model cache was removed, reclaiming about 3.09 GB. Active turbo and pre-existing small comparison caches were preserved. No new dependency, paid API, environment variable, agricultural model, shared API or prediction calculation was introduced.

## Safety and scope

Working database SHA256 before/after all tests:

681bedde9da069e26efa302723aee709ca9c18e9f17478ba774643e1e8332db8

Unchanged. The voice service orchestration module was also unchanged during this retest. No new changes were made to HarvestRoute HTML, its scripts/styles/calculations, dashboard, navigation, other working features, database schemas, authentication, shared API code or agricultural ML assets. Original project/server remain untouched.

### Modified in this retest — 8 files

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/intent_parser.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/routes.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/speech_engine.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/frontend/js/voice-assistant.js`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/static/voice-assistant.js`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/widget.test.cjs`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/README.md`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/VALIDATION_RESULTS.txt`

### Created source/documentation files — 3 files

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/date_words.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/test_multilingual_retest.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/RETEST_RESULTS.md`

### Deleted source files

None. Only this run's disposable regression database and rejected downloaded benchmark-model cache were removed.

### Runtime evidence

Generic input clips, approved reply audio, before/after transcripts, model comparisons, actual backend responses and test logs are local runtime evidence files. The following is the complete current runtime file list; server-8766.log and server-8766.pid existed previously and were updated for the duplicate restart, while the retest artifacts were created in this run:

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/multilingual-retest-audio-final.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/multilingual-retest-audio.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/multilingual-retest-text-final.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/multilingual-retest-text.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/multilingual-retest-tts-final.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/en-IN-0.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/en-IN-1.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/en-IN-2.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/en-IN-3.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/hi-IN-0.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/hi-IN-1.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/hi-IN-2.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/hi-IN-3.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/kn-IN-0.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/kn-IN-1.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/kn-IN-2.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/kn-IN-3.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-en-IN-followup.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-en-IN-historical.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-en-IN-prediction.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-hi-IN-followup.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-hi-IN-historical.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-hi-IN-prediction.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-kn-IN-followup.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-kn-IN-historical.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-audio/reply-kn-IN-prediction.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-baseline.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-full-kannada-translation.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-full-kannada.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-kannada-translation.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-regression-results.txt`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/retest-tuned-speech.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/server-8766.log`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/server-8766.pid`
