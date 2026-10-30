/**
 * CropMandi AI — i18n (Internationalization) System
 *
 * Architecture:
 *  - Three JSON locale files: en.json, hi.json, kn.json
 *  - Translation keys use dot-notation (e.g. "nav.dashboard")
 *  - Language preference is persisted in localStorage
 *  - Switching language updates data-i18n attributes and document lang
 *  - Falls back to English for any missing key
 *
 * Usage in HTML:
 *   <span data-i18n="nav.dashboard">Dashboard</span>
 *   <input data-i18n-placeholder="common.search" placeholder="Search...">
 *   <button data-i18n-aria-label="common.close" aria-label="Close">
 *
 * Usage in JS:
 *   CropMandiI18n.t('nav.dashboard')  → translated string
 *   CropMandiI18n.setLanguage('hi')   → switch to Hindi
 *   CropMandiI18n.getLanguage()       → 'en' | 'hi' | 'kn'
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "cropmandi_language";
  var SUPPORTED = ["en", "hi", "kn"];
  var DEFAULT_LANG = "en";

  /* ─────────────────────────────────────────────
     Language metadata
  ───────────────────────────────────────────── */
  var LANG_META = {
    en: { label: "English",  flag: "🇬🇧", dir: "ltr", htmlLang: "en" },
    hi: { label: "हिंदी",   flag: "🇮🇳", dir: "ltr", htmlLang: "hi" },
    kn: { label: "ಕನ್ನಡ",  flag: "🇮🇳", dir: "ltr", htmlLang: "kn" }
  };

  /* ─────────────────────────────────────────────
     In-memory translation stores
  ───────────────────────────────────────────── */
  var _catalogs = { en: null, hi: null, kn: null };
  var _activeLang = DEFAULT_LANG;
  var _loadedLangs = {};

  /* ─────────────────────────────────────────────
     Resolve the path relative to this script file
     so locale JSON files are found regardless of
     which HTML file loads i18n.js.
  ───────────────────────────────────────────── */
  function _scriptDir() {
    // Find this script's src attribute to derive base path
    var scripts = document.querySelectorAll("script[src]");
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].getAttribute("src");
      if (src && src.indexOf("i18n.js") !== -1) {
        return src.substring(0, src.lastIndexOf("/") + 1);
      }
    }
    // Fallback: guess from current location
    return "";
  }

  /* ─────────────────────────────────────────────
     BUNDLED TRANSLATIONS (inline fallback)
     These are pre-seeded so the UI translates
     immediately on any protocol (file://, http://).
  ───────────────────────────────────────────── */
  var _BUNDLE = {
    en: {"language":{"english":"English","hindi":"हिंदी","kannada":"ಕನ್ನಡ","select":"Select Language"},"brand":{"name":"CropMandi AI","tagline":"Agricultural Intelligence","subtitle":"Smart Decisions, Better Returns"},"nav":{"dashboard":"Dashboard","myCrops":"My Crops","analytics":"Analytics","farmCalendar":"Farm Calendar","alerts":"Alerts","settings":"Settings","logout":"Logout","market":"Market","weather":"Weather","help":"Help","voice":"Voice","home":"Home","crops":"Crops"},"common":{"search":"Search markets, crops...","loading":"Loading...","error":"Error","save":"Save","cancel":"Cancel","update":"Update","submit":"Submit","close":"Close","back":"Back","next":"Next","previous":"Previous","noData":"No data available","tryAgain":"Please try again","applyFilters":"Apply Filters","exportData":"Export Data","viewAll":"View All","setAlert":"Set Alert","refresh":"Refresh","notifications":"Notifications","language":"Language","profile":"Profile","secureAccess":"🔒 Secure access"},"landing":{"hero1":"Know","hero1highlight":"Where.","hero2":"Know","hero2highlight":"When.","hero3":"Earn","hero3highlight":"More.","heroSubtitle":"AI-powered market intelligence that helps farmers sell at the right place and the right time.","getStarted":"Get Started","exploreDashboard":"Explore Dashboard","features":{"apmc":"Best APMC\nRecommendation","price":"Price Prediction\n& Trends","profit":"Expected Profit\nCalculator","voice":"Voice Assistant\nSupport","payments":"Secure Payments\nwith Stripe"}},"auth":{"coffeeAndPepper":"Coffee & Pepper","title":"CropMandi AI","subtitle":"Know the price. Choose the right market. Sell smarter.","description":"Verified market intelligence for Coffee & Pepper growers.","features":{"verifiedPrices":"Verified Prices","marketComparison":"Market Comparison","aiInsights":"AI Insights"},"login":"Log In","register":"Register","phoneOrEmail":"Phone Number or Email","password":"Password","rememberMe":"Remember Me","forgotPassword":"Forgot Password?","accessDashboard":"Access Dashboard →","newToApp":"New to CropMandi?","createAccount":"Create an account","fullName":"Full Name","farmLocation":"Farm Location","primaryCrop":"Primary Crop","mobileNumber":"Mobile Number","email":"Email (optional)","createFarmerAccount":"Create Farmer Account →","alreadyHaveAccount":"Already have an account?","logIn":"Log in","termsAndPrivacy":"Terms & Privacy","agreeText":"By registering, you agree to our","selectMainCrop":"Select main crop","enterPhoneOrEmail":"Enter phone or email","enterPassword":"Enter password","enterEmail":"Enter email","createPassword":"Create a password","farmLocationPlaceholder":"Village, District","fullNamePlaceholder":"e.g. Ramesh Kumar","phonePlaceholder":"+91","crops":{"wheat":"Wheat","rice":"Rice (Paddy)","cotton":"Cotton","sugarcane":"Sugarcane","other":"Other"}},"dashboard":{"greeting":"Good morning","commodity":"Commodity","variety":"Variety","location":"Location","quantity":"Quantity (Quintals)","updateDashboard":"Update Dashboard","currentPrice":"Current price","topObservedCentre":"Top observed centre","priceDate":"Price date","source":"Source","latestObserved":"Latest observed","recordedMarketPrice":"Recorded market price","date":"Date","nextSessionEstimate":"Next-session estimate","baselineOutput":"Baseline output, not an observed price","target":"Target","weather":"Weather","weatherUnavailable":"Weather unavailable","setAlert":"Set Alert","savePrediction":"Save","marketComparison":"Market comparison","loadingMarketPrices":"Loading market prices...","centre":"Centre","price":"Price","priceDate2":"Date","mappedCentres":"Mapped centres","coldStorage":"Cold Storage","coldStorageDesc":"Uses the location selected above. Nearby facilities are labelled when they are not in that village. Availability is never assumed.","crop":"Crop","quantityKg":"Quantity (kg)","farmerLocation":"Farmer location","fromLocationSelector":"From location selector","searchNearby":"Search nearby","searching":"Searching nearby cold storages...","demoPayment":"Demo Payment — Razorpay Test Mode","demoPaymentDesc":"Uses crop and quantity from the Cold Storage section above. Amount is a fixed demo value, not a market price.","quantityKgLabel":"Quantity (kg)","fromColdStorageCrop":"From Cold Storage crop selector","fromColdStorageQty":"From Cold Storage quantity (default 10 kg if blank)","amount":"Amount","demoAmount":"₹100 · fixed demo amount","payButton":"Pay ₹100 (Test Mode)","demoDisclaimer":"Demo payment only. This does not represent a real crop sale, storage booking, or production authentication. The backend uses a demo identity, not a real login.","loadingLocations":"Loading locations…","coffee":"Coffee","blackPepper":"Black Pepper","loading":"Loading...","priceOutlook":"Price Outlook"},"analytics":{"title":"Market Analytics","subtitle":"Deep dive into pricing trends and AI predictions.","cropCardamom":"Crop: Cardamom","cropCoffee":"Crop: Coffee","cropPepper":"Crop: Pepper","varietyAll":"Variety: All","variety8mm":"Variety: 8mm","variety7mm":"Variety: 7mm","stateKarnataka":"State: Karnataka","stateKerala":"State: Kerala","timeLast30":"Time: Last 30 Days","timeLast7":"Time: Last 7 Days","timeYtd":"Time: YTD","avgPriceQtl":"Avg. Price / Qtl","aiPrediction":"AI Prediction","bestApmcRate":"Best APMC Rate","marketTrend":"Market Trend","priceTrend":"Price Trend","loadingVerified":"Loading verified market data...","regionalHeatmap":"Regional Heatmap","regionalDesc":"Price variance across Karnataka APMCs","priceLevel":"Price Level","high":"High","avg":"Avg","apmcComparison":"APMC Market Comparison","detailedBreakdown":"Detailed breakdown of top performing markets","market":"Market (APMC)","todayRate":"Today's Rate (₹/Qtl)","volume":"Volume","predictionWeek":"7-Day Prediction","actionSignal":"Action Signal","loadingData":"Loading verified market data..."},"myCrops":{"title":"My Crops","subtitle":"Manage your registered crops and track their performance"},"farmCalendar":{"title":"Farm Calendar","subtitle":"Plan your agricultural activities and track important dates"},"alerts":{"title":"Alert Center","subtitle":"Stay updated with price alerts and market notifications"},"settings":{"title":"Settings","subtitle":"Manage your account and preferences"},"recommendations":{"sell":"SELL","hold":"HOLD","buyingOpportunity":"BUYING OPPORTUNITY"},"voiceAssistant":"Voice Assistant","errors":{"loadFailed":"Unable to load market data. Please try again.","apiUnavailable":"API unavailable. Please check your connection.","noObservations":"No verified price observations available for this location.","incorrectCredentials":"Incorrect phone/email or password.","accountExists":"An account with this phone or email already exists. Please log in.","enterName":"Please enter your full name.","enterContact":"Please enter a mobile number or email.","shortPassword":"Please choose a password with at least 4 characters.","enterCredentials":"Please enter your phone/email and password."},"success":{"alertSet":"Alert set successfully!","predictionSaved":"Prediction saved!","paymentSuccess":"Payment successful!"}},
    hi: {"language":{"english":"English","hindi":"हिंदी","kannada":"ಕನ್ನಡ","select":"भाषा चुनें"},"brand":{"name":"क्रॉप मंडी AI","tagline":"कृषि बुद्धिमत्ता","subtitle":"स्मार्ट निर्णय, बेहतर आय"},"nav":{"dashboard":"डैशबोर्ड","myCrops":"मेरी फसलें","analytics":"विश्लेषण","farmCalendar":"खेत कैलेंडर","alerts":"अलर्ट","settings":"सेटिंग्स","logout":"लॉगआउट","market":"बाज़ार","weather":"मौसम","help":"सहायता","voice":"आवाज़","home":"होम","crops":"फसलें"},"common":{"search":"बाज़ार, फसलें खोजें...","loading":"लोड हो रहा है...","error":"त्रुटि","save":"सहेजें","cancel":"रद्द करें","update":"अपडेट करें","submit":"सबमिट करें","close":"बंद करें","back":"वापस","next":"आगे","previous":"पिछला","noData":"कोई डेटा उपलब्ध नहीं","tryAgain":"कृपया पुनः प्रयास करें","applyFilters":"फ़िल्टर लागू करें","exportData":"डेटा निर्यात करें","viewAll":"सभी देखें","setAlert":"अलर्ट सेट करें","refresh":"रीफ्रेश","notifications":"सूचनाएं","language":"भाषा","profile":"प्रोफ़ाइल","secureAccess":"🔒 सुरक्षित पहुंच"},"landing":{"hero1":"जानें","hero1highlight":"कहाँ।","hero2":"जानें","hero2highlight":"कब।","hero3":"कमाएं","hero3highlight":"ज़्यादा।","heroSubtitle":"AI-संचालित बाज़ार जानकारी जो किसानों को सही जगह और सही समय पर बेचने में मदद करती है।","getStarted":"शुरू करें","exploreDashboard":"डैशबोर्ड देखें","features":{"apmc":"सर्वश्रेष्ठ APMC\nसिफ़ारिश","price":"मूल्य अनुमान\nऔर रुझान","profit":"अपेक्षित लाभ\nकैलकुलेटर","voice":"वॉयस असिस्टेंट\nसहायता","payments":"Stripe के साथ\nसुरक्षित भुगतान"}},"auth":{"coffeeAndPepper":"कॉफी और काली मिर्च","title":"क्रॉप मंडी AI","subtitle":"कीमत जानें। सही बाज़ार चुनें। स्मार्ट तरीके से बेचें।","description":"कॉफी और काली मिर्च उगाने वालों के लिए सत्यापित बाज़ार जानकारी।","features":{"verifiedPrices":"सत्यापित कीमतें","marketComparison":"बाज़ार तुलना","aiInsights":"AI अंतर्दृष्टि"},"login":"लॉग इन","register":"पंजीकरण","phoneOrEmail":"फोन नंबर या ईमेल","password":"पासवर्ड","rememberMe":"याद रखें","forgotPassword":"पासवर्ड भूल गए?","accessDashboard":"डैशबोर्ड खोलें →","newToApp":"क्रॉप मंडी में नए हैं?","createAccount":"खाता बनाएं","fullName":"पूरा नाम","farmLocation":"खेत का स्थान","primaryCrop":"मुख्य फसल","mobileNumber":"मोबाइल नंबर","email":"ईमेल (वैकल्पिक)","createFarmerAccount":"किसान खाता बनाएं →","alreadyHaveAccount":"पहले से खाता है?","logIn":"लॉग इन करें","termsAndPrivacy":"नियम और गोपनीयता","agreeText":"पंजीकरण करके, आप हमारी सहमति देते हैं","selectMainCrop":"मुख्य फसल चुनें","enterPhoneOrEmail":"फोन या ईमेल दर्ज करें","enterPassword":"पासवर्ड दर्ज करें","enterEmail":"ईमेल दर्ज करें","createPassword":"पासवर्ड बनाएं","farmLocationPlaceholder":"गांव, जिला","fullNamePlaceholder":"जैसे रमेश कुमार","phonePlaceholder":"+91","crops":{"wheat":"गेहूं","rice":"चावल (धान)","cotton":"कपास","sugarcane":"गन्ना","other":"अन्य"}},"dashboard":{"greeting":"सुप्रभात","commodity":"फसल","variety":"किस्म","location":"स्थान","quantity":"मात्रा (क्विंटल)","updateDashboard":"डैशबोर्ड अपडेट करें","currentPrice":"वर्तमान मूल्य","topObservedCentre":"शीर्ष देखा गया केंद्र","priceDate":"मूल्य तिथि","source":"स्रोत","latestObserved":"नवीनतम देखा गया","recordedMarketPrice":"दर्ज बाज़ार मूल्य","date":"तिथि","nextSessionEstimate":"अगले सत्र का अनुमान","baselineOutput":"आधारभूत आउटपुट, देखी गई कीमत नहीं","target":"लक्ष्य","weather":"मौसम","weatherUnavailable":"मौसम उपलब्ध नहीं","setAlert":"अलर्ट सेट करें","savePrediction":"सहेजें","marketComparison":"बाज़ार तुलना","loadingMarketPrices":"बाज़ार मूल्य लोड हो रहे हैं...","centre":"केंद्र","price":"मूल्य","priceDate2":"तिथि","mappedCentres":"मैप किए गए केंद्र","coldStorage":"शीत भंडारण","coldStorageDesc":"ऊपर चुने गए स्थान का उपयोग करता है।","crop":"फसल","quantityKg":"मात्रा (किग्रा)","farmerLocation":"किसान का स्थान","fromLocationSelector":"स्थान चयनकर्ता से","searchNearby":"नज़दीकी खोजें","searching":"नज़दीकी शीत भंडारण खोज रहे हैं...","demoPayment":"डेमो भुगतान — Razorpay टेस्ट मोड","demoPaymentDesc":"डेमो मूल्य, बाज़ार मूल्य नहीं।","quantityKgLabel":"मात्रा (किग्रा)","fromColdStorageCrop":"शीत भंडारण फसल चयनकर्ता से","fromColdStorageQty":"शीत भंडारण मात्रा से","amount":"राशि","demoAmount":"₹100 · निश्चित डेमो राशि","payButton":"₹100 का भुगतान करें (टेस्ट मोड)","demoDisclaimer":"केवल डेमो भुगतान।","loadingLocations":"स्थान लोड हो रहे हैं…","coffee":"कॉफी","blackPepper":"काली मिर्च","loading":"लोड हो रहा है...","priceOutlook":"मूल्य दृष्टिकोण"},"analytics":{"title":"बाज़ार विश्लेषण","subtitle":"मूल्य रुझानों और AI भविष्यवाणियों में गहराई से जाएं।","cropCardamom":"फसल: इलायची","cropCoffee":"फसल: कॉफी","cropPepper":"फसल: काली मिर्च","varietyAll":"किस्म: सभी","variety8mm":"किस्म: 8mm","variety7mm":"किस्म: 7mm","stateKarnataka":"राज्य: कर्नाटक","stateKerala":"राज्य: केरल","timeLast30":"समय: पिछले 30 दिन","timeLast7":"समय: पिछले 7 दिन","timeYtd":"समय: इस साल","avgPriceQtl":"औसत मूल्य / क्विंटल","aiPrediction":"AI भविष्यवाणी","bestApmcRate":"सर्वश्रेष्ठ APMC दर","marketTrend":"बाज़ार रुझान","priceTrend":"मूल्य रुझान","loadingVerified":"सत्यापित बाज़ार डेटा लोड हो रहा है...","regionalHeatmap":"क्षेत्रीय हीटमैप","regionalDesc":"कर्नाटक APMC में मूल्य भिन्नता","priceLevel":"मूल्य स्तर","high":"उच्च","avg":"औसत","apmcComparison":"APMC बाज़ार तुलना","detailedBreakdown":"शीर्ष प्रदर्शन करने वाले बाज़ारों का विवरण","market":"बाज़ार (APMC)","todayRate":"आज की दर (₹/क्विंटल)","volume":"मात्रा","predictionWeek":"7-दिन की भविष्यवाणी","actionSignal":"कार्रवाई संकेत","loadingData":"सत्यापित बाज़ार डेटा लोड हो रहा है..."},"myCrops":{"title":"मेरी फसलें","subtitle":"अपनी पंजीकृत फसलों का प्रबंधन करें"},"farmCalendar":{"title":"खेत कैलेंडर","subtitle":"कृषि गतिविधियों की योजना बनाएं"},"alerts":{"title":"अलर्ट केंद्र","subtitle":"मूल्य अलर्ट के साथ अपडेट रहें"},"settings":{"title":"सेटिंग्स","subtitle":"खाता और प्राथमिकताएं प्रबंधित करें"},"recommendations":{"sell":"बेचें","hold":"रोकें","buyingOpportunity":"खरीद का अवसर"},"voiceAssistant":"वॉयस असिस्टेंट","errors":{"loadFailed":"बाज़ार डेटा लोड करने में असमर्थ।","apiUnavailable":"API अनुपलब्ध।","noObservations":"इस स्थान के लिए कोई मूल्य उपलब्ध नहीं।","incorrectCredentials":"गलत फोन/ईमेल या पासवर्ड।","accountExists":"खाता पहले से मौजूद है।","enterName":"पूरा नाम दर्ज करें।","enterContact":"मोबाइल नंबर या ईमेल दर्ज करें।","shortPassword":"कम से कम 4 अक्षरों का पासवर्ड चुनें।","enterCredentials":"फोन/ईमेल और पासवर्ड दर्ज करें।"},"success":{"alertSet":"अलर्ट सफलतापूर्वक सेट किया गया!","predictionSaved":"भविष्यवाणी सहेजी गई!","paymentSuccess":"भुगतान सफल!"}},
    kn: {"language":{"english":"English","hindi":"हिंदी","kannada":"ಕನ್ನಡ","select":"ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ"},"brand":{"name":"ಕ್ರಾಪ್ ಮಂಡಿ AI","tagline":"ಕೃಷಿ ಬುದ್ಧಿಮತ್ತೆ","subtitle":"ಸ್ಮಾರ್ಟ್ ನಿರ್ಧಾರಗಳು, ಉತ್ತಮ ಆದಾಯ"},"nav":{"dashboard":"ಡ್ಯಾಶ್‌ಬೋರ್ಡ್","myCrops":"ನನ್ನ ಬೆಳೆಗಳು","analytics":"ವಿಶ್ಲೇಷಣೆ","farmCalendar":"ಕೃಷಿ ಕ್ಯಾಲೆಂಡರ್","alerts":"ಎಚ್ಚರಿಕೆಗಳು","settings":"ಸೆಟ್ಟಿಂಗ್‌ಗಳು","logout":"ಲಾಗ್ ಔಟ್","market":"ಮಾರುಕಟ್ಟೆ","weather":"ಹವಾಮಾನ","help":"ಸಹಾಯ","voice":"ಧ್ವನಿ","home":"ಮುಖಪುಟ","crops":"ಬೆಳೆಗಳು"},"common":{"search":"ಮಾರುಕಟ್ಟೆ, ಬೆಳೆಗಳನ್ನು ಹುಡುಕಿ...","loading":"ಲೋಡ್ ಆಗುತ್ತಿದೆ...","error":"ದೋಷ","save":"ಉಳಿಸಿ","cancel":"ರದ್ದು ಮಾಡಿ","update":"ಅಪ್‌ಡೇಟ್ ಮಾಡಿ","submit":"ಸಲ್ಲಿಸಿ","close":"ಮುಚ್ಚಿ","back":"ಹಿಂದೆ","next":"ಮುಂದೆ","previous":"ಹಿಂದಿನ","noData":"ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ","tryAgain":"ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ","applyFilters":"ಫಿಲ್ಟರ್‌ಗಳನ್ನು ಅನ್ವಯಿಸಿ","exportData":"ಡೇಟಾ ರಫ್ತು ಮಾಡಿ","viewAll":"ಎಲ್ಲವನ್ನು ನೋಡಿ","setAlert":"ಎಚ್ಚರಿಕೆ ಹೊಂದಿಸಿ","refresh":"ರಿಫ್ರೆಶ್","notifications":"ಅಧಿಸೂಚನೆಗಳು","language":"ಭಾಷೆ","profile":"ಪ್ರೊಫೈಲ್","secureAccess":"🔒 ಸುರಕ್ಷಿತ ಪ್ರವೇಶ"},"landing":{"hero1":"ತಿಳಿಯಿರಿ","hero1highlight":"ಎಲ್ಲಿ.","hero2":"ತಿಳಿಯಿರಿ","hero2highlight":"ಯಾವಾಗ.","hero3":"ಗಳಿಸಿ","hero3highlight":"ಹೆಚ್ಚು.","heroSubtitle":"AI-ಚಾಲಿತ ಮಾರುಕಟ್ಟೆ ಮಾಹಿತಿ ರೈತರಿಗೆ ಸರಿಯಾದ ಸ್ಥಳ ಮತ್ತು ಸಮಯದಲ್ಲಿ ಮಾರಾಟ ಮಾಡಲು ಸಹಾಯ.","getStarted":"ಪ್ರಾರಂಭಿಸಿ","exploreDashboard":"ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಅನ್ವೇಷಿಸಿ","features":{"apmc":"ಅತ್ಯುತ್ತಮ APMC\nಶಿಫಾರಸು","price":"ಬೆಲೆ ಮುನ್ಸೂಚನೆ\nಮತ್ತು ಪ್ರವೃತ್ತಿ","profit":"ನಿರೀಕ್ಷಿತ ಲಾಭ\nಕ್ಯಾಲ್ಕುಲೇಟರ್","voice":"ಧ್ವನಿ ಸಹಾಯಕ\nಬೆಂಬಲ","payments":"Stripe ಜೊತೆ\nಸುರಕ್ಷಿತ ಪಾವತಿ"}},"auth":{"coffeeAndPepper":"ಕಾಫಿ ಮತ್ತು ಕಾಳು ಮೆಣಸು","title":"ಕ್ರಾಪ್ ಮಂಡಿ AI","subtitle":"ಬೆಲೆ ತಿಳಿಯಿರಿ. ಸರಿಯಾದ ಮಾರುಕಟ್ಟೆ ಆಯ್ಕೆ ಮಾಡಿ. ಜಾಣ್ಮೆಯಿಂದ ಮಾರಿ.","description":"ಕಾಫಿ ಮತ್ತು ಕಾಳು ಮೆಣಸು ಬೆಳೆಗಾರರಿಗೆ ಮಾಹಿತಿ.","features":{"verifiedPrices":"ಪರಿಶೀಲಿಸಿದ ಬೆಲೆಗಳು","marketComparison":"ಮಾರುಕಟ್ಟೆ ಹೋಲಿಕೆ","aiInsights":"AI ಒಳನೋಟಗಳು"},"login":"ಲಾಗ್ ಇನ್","register":"ನೋಂದಣಿ","phoneOrEmail":"ಫೋನ್ ಸಂಖ್ಯೆ ಅಥವಾ ಇಮೇಲ್","password":"ಪಾಸ್‌ವರ್ಡ್","rememberMe":"ನೆನಪಿಡಿ","forgotPassword":"ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿದ್ದೀರಾ?","accessDashboard":"ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ತೆರೆಯಿರಿ →","newToApp":"CropMandi ಗೆ ಹೊಸಬರೇ?","createAccount":"ಖಾತೆ ರಚಿಸಿ","fullName":"ಪೂರ್ಣ ಹೆಸರು","farmLocation":"ಕೃಷಿ ಸ್ಥಳ","primaryCrop":"ಪ್ರಾಥಮಿಕ ಬೆಳೆ","mobileNumber":"ಮೊಬೈಲ್ ಸಂಖ್ಯೆ","email":"ಇಮೇಲ್ (ಐಚ್ಛಿಕ)","createFarmerAccount":"ರೈತ ಖಾತೆ ರಚಿಸಿ →","alreadyHaveAccount":"ಈಗಾಗಲೇ ಖಾತೆ ಇದೆಯೇ?","logIn":"ಲಾಗ್ ಇನ್ ಮಾಡಿ","termsAndPrivacy":"ನಿಯಮಗಳು ಮತ್ತು ಗೌಪ್ಯತೆ","agreeText":"ನೋಂದಣಿ ಮಾಡುವ ಮೂಲಕ ನೀವು ಸಮ್ಮತಿಸುತ್ತೀರಿ","selectMainCrop":"ಮುಖ್ಯ ಬೆಳೆ ಆಯ್ಕೆ ಮಾಡಿ","enterPhoneOrEmail":"ಫೋನ್ ಅಥವಾ ಇಮೇಲ್ ನಮೂದಿಸಿ","enterPassword":"ಪಾಸ್‌ವರ್ಡ್ ನಮೂದಿಸಿ","enterEmail":"ಇಮೇಲ್ ನಮೂದಿಸಿ","createPassword":"ಪಾಸ್‌ವರ್ಡ್ ರಚಿಸಿ","farmLocationPlaceholder":"ಗ್ರಾಮ, ಜಿಲ್ಲೆ","fullNamePlaceholder":"ಉದಾ. ರಮೇಶ್ ಕುಮಾರ್","phonePlaceholder":"+91","crops":{"wheat":"ಗೋಧಿ","rice":"ಅಕ್ಕಿ (ಭತ್ತ)","cotton":"ಹತ್ತಿ","sugarcane":"ಕಬ್ಬು","other":"ಇತರೆ"}},"dashboard":{"greeting":"ಶುಭ ಬೆಳಗು","commodity":"ಬೆಳೆ","variety":"ತಳಿ","location":"ಸ್ಥಳ","quantity":"ಪ್ರಮಾಣ (ಕ್ವಿಂಟಾಲ್)","updateDashboard":"ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಅಪ್‌ಡೇಟ್ ಮಾಡಿ","currentPrice":"ಪ್ರಸ್ತುತ ಬೆಲೆ","topObservedCentre":"ಅತ್ಯುತ್ತಮ ಗಮನಿಸಿದ ಕೇಂದ್ರ","priceDate":"ಬೆಲೆ ದಿನಾಂಕ","source":"ಮೂಲ","latestObserved":"ಇತ್ತೀಚೆಗೆ ಗಮನಿಸಿದ","recordedMarketPrice":"ದಾಖಲಾದ ಮಾರುಕಟ್ಟೆ ಬೆಲೆ","date":"ದಿನಾಂಕ","nextSessionEstimate":"ಮುಂದಿನ ಸೆಷನ್ ಅಂದಾಜು","baselineOutput":"ಆಧಾರ ಉತ್ಪಾದನೆ, ಗಮನಿಸಿದ ಬೆಲೆ ಅಲ್ಲ","target":"ಗುರಿ","weather":"ಹವಾಮಾನ","weatherUnavailable":"ಹವಾಮಾನ ಲಭ್ಯವಿಲ್ಲ","setAlert":"ಎಚ್ಚರಿಕೆ ಹೊಂದಿಸಿ","savePrediction":"ಉಳಿಸಿ","marketComparison":"ಮಾರುಕಟ್ಟೆ ಹೋಲಿಕೆ","loadingMarketPrices":"ಮಾರುಕಟ್ಟೆ ಬೆಲೆಗಳು ಲೋಡ್ ಆಗುತ್ತಿವೆ...","centre":"ಕೇಂದ್ರ","price":"ಬೆಲೆ","priceDate2":"ದಿನಾಂಕ","mappedCentres":"ಮ್ಯಾಪ್ ಮಾಡಿದ ಕೇಂದ್ರಗಳು","coldStorage":"ಶೀತಲ ಸಂಗ್ರಹ","coldStorageDesc":"ಮೇಲೆ ಆಯ್ಕೆ ಮಾಡಿದ ಸ್ಥಳವನ್ನು ಬಳಸುತ್ತದೆ.","crop":"ಬೆಳೆ","quantityKg":"ಪ್ರಮಾಣ (ಕಿಗ್ರಾ)","farmerLocation":"ರೈತರ ಸ್ಥಳ","fromLocationSelector":"ಸ್ಥಳ ಆಯ್ಕೆಗಾರರಿಂದ","searchNearby":"ಸಮೀಪ ಹುಡುಕಿ","searching":"ಹತ್ತಿರದ ಶೀತಲ ಸಂಗ್ರಹ ಹುಡುಕುತ್ತಿದೆ...","demoPayment":"ಡೆಮೋ ಪಾವತಿ — Razorpay ಟೆಸ್ಟ್ ಮೋಡ್","demoPaymentDesc":"ಡೆಮೋ ಮೌಲ್ಯ.","quantityKgLabel":"ಪ್ರಮಾಣ (ಕಿಗ್ರಾ)","fromColdStorageCrop":"ಶೀತಲ ಸಂಗ್ರಹ ಬೆಳೆ ಆಯ್ಕೆಗಾರರಿಂದ","fromColdStorageQty":"ಶೀತಲ ಸಂಗ್ರಹ ಪ್ರಮಾಣದಿಂದ","amount":"ಮೊತ್ತ","demoAmount":"₹100 · ಸ್ಥಿರ ಡೆಮೋ ಮೊತ್ತ","payButton":"₹100 ಪಾವತಿಸಿ (ಟೆಸ್ಟ್ ಮೋಡ್)","demoDisclaimer":"ಕೇವಲ ಡೆಮೋ ಪಾವತಿ.","loadingLocations":"ಸ್ಥಳಗಳು ಲೋಡ್ ಆಗುತ್ತಿವೆ…","coffee":"ಕಾಫಿ","blackPepper":"ಕಾಳು ಮೆಣಸು","loading":"ಲೋಡ್ ಆಗುತ್ತಿದೆ...","priceOutlook":"ಬೆಲೆ ನಿರೀಕ್ಷೆ"},"analytics":{"title":"ಮಾರುಕಟ್ಟೆ ವಿಶ್ಲೇಷಣೆ","subtitle":"ಬೆಲೆ ಪ್ರವೃತ್ತಿ ಮತ್ತು AI ಮುನ್ಸೂಚನೆಗಳು.","cropCardamom":"ಬೆಳೆ: ಏಲಕ್ಕಿ","cropCoffee":"ಬೆಳೆ: ಕಾಫಿ","cropPepper":"ಬೆಳೆ: ಕಾಳು ಮೆಣಸು","varietyAll":"ತಳಿ: ಎಲ್ಲ","variety8mm":"ತಳಿ: 8mm","variety7mm":"ತಳಿ: 7mm","stateKarnataka":"ರಾಜ್ಯ: ಕರ್ನಾಟಕ","stateKerala":"ರಾಜ್ಯ: ಕೇರಳ","timeLast30":"ಸಮಯ: ಕಳೆದ 30 ದಿನಗಳು","timeLast7":"ಸಮಯ: ಕಳೆದ 7 ದಿನಗಳು","timeYtd":"ಸಮಯ: ಈ ವರ್ಷ","avgPriceQtl":"ಸರಾಸರಿ ಬೆಲೆ / ಕ್ವಿಂ","aiPrediction":"AI ಮುನ್ಸೂಚನೆ","bestApmcRate":"ಅತ್ಯುತ್ತಮ APMC ದರ","marketTrend":"ಮಾರುಕಟ್ಟೆ ಪ್ರವೃತ್ತಿ","priceTrend":"ಬೆಲೆ ಪ್ರವೃತ್ತಿ","loadingVerified":"ಡೇಟಾ ಲೋಡ್ ಆಗುತ್ತಿದೆ...","regionalHeatmap":"ಪ್ರಾದೇಶಿಕ ಉಷ್ಣ ನಕ್ಷೆ","regionalDesc":"ಕರ್ನಾಟಕ APMC ಗಳಲ್ಲಿ ಬೆಲೆ ವ್ಯತ್ಯಾಸ","priceLevel":"ಬೆಲೆ ಮಟ್ಟ","high":"ಹೆಚ್ಚು","avg":"ಸರಾಸರಿ","apmcComparison":"APMC ಮಾರುಕಟ್ಟೆ ಹೋಲಿಕೆ","detailedBreakdown":"ಅಗ್ರ ಮಾರುಕಟ್ಟೆಗಳ ವಿವರ","market":"ಮಾರುಕಟ್ಟೆ (APMC)","todayRate":"ಇಂದಿನ ದರ (₹/ಕ್ವಿಂ)","volume":"ಪ್ರಮಾಣ","predictionWeek":"7-ದಿನದ ಮುನ್ಸೂಚನೆ","actionSignal":"ಕ್ರಿಯಾ ಸಂಕೇತ","loadingData":"ಡೇಟಾ ಲೋಡ್ ಆಗುತ್ತಿದೆ..."},"myCrops":{"title":"ನನ್ನ ಬೆಳೆಗಳು","subtitle":"ನಿಮ್ಮ ಬೆಳೆಗಳನ್ನು ನಿರ್ವಹಿಸಿ"},"farmCalendar":{"title":"ಕೃಷಿ ಕ್ಯಾಲೆಂಡರ್","subtitle":"ಕೃಷಿ ಚಟುವಟಿಕೆಗಳನ್ನು ಯೋಜಿಸಿ"},"alerts":{"title":"ಎಚ್ಚರಿಕೆ ಕೇಂದ್ರ","subtitle":"ಎಚ್ಚರಿಕೆಗಳೊಂದಿಗೆ ಅಪ್‌ಡೇಟ್ ಆಗಿರಿ"},"settings":{"title":"ಸೆಟ್ಟಿಂಗ್‌ಗಳು","subtitle":"ಖಾತೆ ಮತ್ತು ಆದ್ಯತೆಗಳನ್ನು ನಿರ್ವಹಿಸಿ"},"recommendations":{"sell":"ಮಾರಿ","hold":"ಇರಿಸಿ","buyingOpportunity":"ಖರೀದಿ ಅವಕಾಶ"},"voiceAssistant":"ಧ್ವನಿ ಸಹಾಯಕ","errors":{"loadFailed":"ಮಾರುಕಟ್ಟೆ ಡೇಟಾ ಲೋಡ್ ಮಾಡಲು ಸಾಧ್ಯವಿಲ್ಲ.","apiUnavailable":"API ಲಭ್ಯವಿಲ್ಲ.","noObservations":"ಈ ಸ್ಥಳಕ್ಕೆ ಬೆಲೆ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ.","incorrectCredentials":"ತಪ್ಪಾದ ಫೋನ್/ಇಮೇಲ್ ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್.","accountExists":"ಖಾತೆ ಈಗಾಗಲೇ ಇದೆ.","enterName":"ಪೂರ್ಣ ಹೆಸರು ನಮೂದಿಸಿ.","enterContact":"ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಅಥವಾ ಇಮೇಲ್ ನಮೂದಿಸಿ.","shortPassword":"ಕನಿಷ್ಠ 4 ಅಕ್ಷರಗಳ ಪಾಸ್‌ವರ್ಡ್ ಆಯ್ಕೆ ಮಾಡಿ.","enterCredentials":"ಫೋನ್/ಇಮೇಲ್ ಮತ್ತು ಪಾಸ್‌ವರ್ಡ್ ನಮೂದಿಸಿ."},"success":{"alertSet":"ಎಚ್ಚರಿಕೆ ಯಶಸ್ವಿಯಾಗಿ ಹೊಂದಿಸಲಾಗಿದೆ!","predictionSaved":"ಮುನ್ಸೂಚನೆ ಉಳಿಸಲಾಗಿದೆ!","paymentSuccess":"ಪಾವತಿ ಯಶಸ್ವಿ!"}}
  };

  /* Pre-seed catalogs from bundle so translations are immediate */
  Object.keys(_BUNDLE).forEach(function (lang) {
    _catalogs[lang] = _BUNDLE[lang];
    _loadedLangs[lang] = true;
  });

  /* ─────────────────────────────────────────────
     Load a single locale JSON file via fetch
     (optional updater — not required for operation)
  ───────────────────────────────────────────── */
  function _loadLocale(lang) {
    /* Already loaded from bundle — just return */
    if (_loadedLangs[lang] && _catalogs[lang] && Object.keys(_catalogs[lang]).length > 1) {
      return Promise.resolve(_catalogs[lang]);
    }
    var base = _scriptDir();
    var url = base + "locales/" + lang + ".json";

    return fetch(url)
      .then(function (res) {
        if (!res.ok) { throw new Error("Failed to load locale: " + lang); }
        return res.json();
      })
      .then(function (data) {
        _catalogs[lang] = data;
        _loadedLangs[lang] = true;
        return data;
      })
      .catch(function (err) {
        console.warn("[CropMandiI18n] Using bundled locale for '" + lang + "' (fetch failed):", err.message);
        _catalogs[lang] = _BUNDLE[lang] || {};
        _loadedLangs[lang] = true;
        return _catalogs[lang];
      });
  }

  /* ─────────────────────────────────────────────
     Resolve a dot-notation key against a catalog
  ───────────────────────────────────────────── */
  function _resolve(catalog, key) {
    if (!catalog) return undefined;
    var parts = key.split(".");
    var node = catalog;
    for (var i = 0; i < parts.length; i++) {
      if (node === null || typeof node !== "object") return undefined;
      node = node[parts[i]];
    }
    return typeof node === "string" ? node : undefined;
  }

  /* ─────────────────────────────────────────────
     Public: translate a key with optional fallback
  ───────────────────────────────────────────── */
  function t(key, fallback) {
    var value = _resolve(_catalogs[_activeLang], key);
    if (value !== undefined) return value;
    // Fallback to English
    if (_activeLang !== DEFAULT_LANG) {
      var enValue = _resolve(_catalogs[DEFAULT_LANG], key);
      if (enValue !== undefined) return enValue;
    }
    // Return provided fallback or the key itself
    return typeof fallback === "string" ? fallback : key;
  }

  /* ─────────────────────────────────────────────
     Apply translations to all data-i18n elements
  ───────────────────────────────────────────── */
  function _applyTranslations() {
    // Text content
    var elements = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      var key = el.getAttribute("data-i18n");
      if (key) {
        el.textContent = t(key);
      }
    }

    // Placeholder attributes
    var placeholders = document.querySelectorAll("[data-i18n-placeholder]");
    for (var j = 0; j < placeholders.length; j++) {
      var pel = placeholders[j];
      var pkey = pel.getAttribute("data-i18n-placeholder");
      if (pkey) {
        pel.setAttribute("placeholder", t(pkey));
      }
    }

    // aria-label attributes
    var ariaEls = document.querySelectorAll("[data-i18n-aria-label]");
    for (var k = 0; k < ariaEls.length; k++) {
      var ael = ariaEls[k];
      var akey = ael.getAttribute("data-i18n-aria-label");
      if (akey) {
        ael.setAttribute("aria-label", t(akey));
      }
    }

    // title attributes
    var titleEls = document.querySelectorAll("[data-i18n-title]");
    for (var l = 0; l < titleEls.length; l++) {
      var tel = titleEls[l];
      var tkey = tel.getAttribute("data-i18n-title");
      if (tkey) {
        tel.setAttribute("title", t(tkey));
      }
    }

    // Update document language
    var meta = LANG_META[_activeLang];
    if (meta) {
      document.documentElement.setAttribute("lang", meta.htmlLang);
    }

    // Update page title if it has a data-i18n-title attribute
    var titleTag = document.querySelector("title[data-i18n]");
    if (titleTag) {
      titleTag.textContent = t(titleTag.getAttribute("data-i18n"));
    }

    // Fire a custom event so other scripts can react
    document.dispatchEvent(new CustomEvent("cropmandi:langchange", {
      detail: { lang: _activeLang, meta: meta }
    }));
  }

  /* ─────────────────────────────────────────────
     Public: switch language
  ───────────────────────────────────────────── */
  function setLanguage(lang, callback) {
    if (SUPPORTED.indexOf(lang) === -1) {
      console.warn("[CropMandiI18n] Unsupported language:", lang);
      return;
    }
    _activeLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);

    // Ensure both the target locale AND English (for fallback) are loaded
    var promises = [_loadLocale(lang)];
    if (lang !== DEFAULT_LANG) {
      promises.push(_loadLocale(DEFAULT_LANG));
    }
    Promise.all(promises).then(function () {
      _applyTranslations();
      _updateSwitcherUI();
      if (typeof callback === "function") callback(lang);
    });
  }

  /* ─────────────────────────────────────────────
     Public: get current language code
  ───────────────────────────────────────────── */
  function getLanguage() {
    return _activeLang;
  }

  /* ─────────────────────────────────────────────
     Update language switcher button labels
  ───────────────────────────────────────────── */
  function _updateSwitcherUI() {
    var meta = LANG_META[_activeLang];
    if (!meta) return;

    // Update all language-current-label spans
    var labels = document.querySelectorAll(".lang-current-label");
    for (var i = 0; i < labels.length; i++) {
      labels[i].textContent = meta.label;
    }

    // Update active state on dropdown items
    var items = document.querySelectorAll("[data-lang]");
    for (var j = 0; j < items.length; j++) {
      var item = items[j];
      var isActive = item.getAttribute("data-lang") === _activeLang;
      item.classList.toggle("lang-option--active", isActive);
      item.setAttribute("aria-checked", isActive ? "true" : "false");
    }
  }

  /* ─────────────────────────────────────────────
     Initialize: read saved preference, load
     English (always), then the saved lang
  ───────────────────────────────────────────── */
  function init() {
    var saved = localStorage.getItem(STORAGE_KEY);
    _activeLang = (saved && SUPPORTED.indexOf(saved) !== -1) ? saved : DEFAULT_LANG;

    // Always load English for fallback
    var toLoad = [_loadLocale(DEFAULT_LANG)];
    if (_activeLang !== DEFAULT_LANG) {
      toLoad.push(_loadLocale(_activeLang));
    }

    Promise.all(toLoad).then(function () {
      _applyTranslations();
      _updateSwitcherUI();
    });
  }

  /* ─────────────────────────────────────────────
     Expose public API
  ───────────────────────────────────────────── */
  global.CropMandiI18n = {
    t: t,
    setLanguage: setLanguage,
    getLanguage: getLanguage,
    langMeta: LANG_META,
    supported: SUPPORTED,
    init: init,
    applyTranslations: _applyTranslations
  };

  // Auto-initialize on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})(window);
