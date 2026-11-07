"""Voice-only orchestration of existing CropMandi services; no model or DB writes."""
from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any

from .project_adapter import crop_rows, _norm


def localize(lang, en, hi, kn):
    return {"en": en, "hi": hi, "kn": kn}.get(lang, en)


def amount(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite service value")
    return f"{value:,.2f}".rstrip("0").rstrip(".")


class AssistantService:
    def __init__(self, price_lookup):
        self.price_lookup = price_lookup
        self.session_factory = getattr(price_lookup, "session_factory", None)

    def __call__(self, intent, p, lang):
        handler = getattr(self, intent, None)
        if handler is None:
            return None
        if not self.session_factory:
            return {"answer": localize(lang, "This data service is not connected.", "यह डेटा सेवा जुड़ी नहीं है।", "ಈ ಡೇಟಾ ಸೇವೆ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ.")}
        return handler(p, lang)

    def inventory_context(self, p, lang):
        """Resolve only unambiguous existing inventory selections on My Crops."""
        if not self.session_factory or "my_crops" not in str(p.get("page")) or not p.get("commodity"):
            return None
        from sqlalchemy import select
        from cropmandi.db.models import FarmerCrop
        crop = "paddy" if p["commodity"] == "rice" else p["commodity"]
        session = self.session_factory()
        try:
            rows = session.scalars(select(FarmerCrop).where(FarmerCrop.commodity == crop)).all()
            if p.get("variety"):
                rows = [r for r in rows if _norm(r.variety) == _norm(p["variety"])]
            if p.get("market"):
                rows = [r for r in rows if _norm(r.location) == _norm(p["market"])]
            if not rows:
                return None
            identities = {(r.variety, r.location) for r in rows}
            if len(identities) > 1 and (not p.get("variety") or not p.get("market")):
                choices = "; ".join(f"{v}, {m}" for v,m in sorted(identities))
                return {"answer": localize(lang, f"Your app inventory has several matching crops. Which one? {choices}", f"ऐप में कई मिलती फसलें हैं। कौन सी? {choices}", f"ಅಪ್ಲಿಕೇಶನ್‌ನಲ್ಲಿ ಹಲವು ಹೊಂದುವ ಬೆಳೆಗಳಿವೆ. ಯಾವುದು? {choices}"), "needs_clarification": True}
            if len(identities) == 1:
                p.setdefault("inventory_source", "existing app inventory")
                p["market"] = p.get("market") or rows[0].location
                p["variety"] = p.get("variety") or rows[0].variety
                if len(rows) == 1:
                    p["quantity"] = p.get("quantity") or rows[0].quantity
                    p["quantity_unit"] = p.get("quantity_unit") or rows[0].unit
        finally:
            session.close()
        return None

    def missing(self, p, lang, *fields):
        absent = [f for f in fields if p.get(f) in (None, "")]
        if not absent:
            return None
        names = {"commodity": ("crop", "फसल", "ಬೆಳೆ"), "market": ("market", "मंडी", "ಮಾರುಕಟ್ಟೆ"),
                 "origin": ("farm origin", "खेत का स्थान", "ಹೊಲದ ಸ್ಥಳ"),
                 "variety": ("variety", "किस्म", "ತಳಿ"), "grade": ("grade", "ग्रेड", "ಗ್ರೇಡ್"),
                 "quantity": ("quantity", "मात्रा", "ಪ್ರಮಾಣ"), "quantity_unit": ("quantity unit (kg or quintal)", "मात्रा की इकाई", "ಪ್ರಮಾಣದ ಘಟಕ")}
        index = {"en": 0, "hi": 1, "kn": 2}.get(lang, 0)
        label = ", ".join(names.get(f, (f, f, f))[index] for f in absent)
        return {"answer": localize(lang, f"Please specify {label}.", f"कृपया {label} बताइए।", f"ದಯವಿಟ್ಟು {label} ತಿಳಿಸಿ."), "needs_clarification": True}

    def compare_prices(self, p, lang):
        missing = self.missing(p, lang, "commodity", "market")
        if missing:
            return missing
        # Comparisons are exact calendar dates, never nearest available sessions.
        today = date.fromisoformat(p["client_date"])
        first_date = date.fromisoformat(p.get("arrival_date") or today.isoformat())
        dates = [today.isoformat(), (today - timedelta(days=1)).isoformat()] if first_date == today or first_date == today - timedelta(days=1) else [first_date.isoformat(), (first_date - timedelta(days=1)).isoformat()]
        dates = p.get("comparison_dates") or dates
        records = [self.price_lookup({**p, "arrival_date": d}) for d in dates]
        if any(not r or r.get("needs_variety") for r in records):
            return {"answer": localize(lang, f"Matching recorded prices are unavailable or ambiguous for {p['commodity']} at {p['market']} on {dates[0]} and {dates[1]}. Please select a variety and grade.", f"{p['market']} में {p['commodity']} के {dates[0]} और {dates[1]} के मिलते भाव उपलब्ध या स्पष्ट नहीं हैं। किस्म और ग्रेड चुनें।", f"{p['market']} ನಲ್ಲಿ {p['commodity']} ಗೆ {dates[0]} ಮತ್ತು {dates[1]} ರ ಹೊಂದಾಣಿಕೆಯ ಬೆಲೆ ಲಭ್ಯವಿಲ್ಲ ಅಥವಾ ಅಸ್ಪಷ್ಟವಾಗಿದೆ. ತಳಿ ಮತ್ತು ಗ್ರೇಡ್ ಆಯ್ಕೆಮಾಡಿ."), "records": records, "needs_clarification": True}
        a,b = records
        if any(_norm(a.get(k)) != _norm(b.get(k)) for k in ("unit", "series", "grade", "market")):
            return {"answer": localize(lang, "These records use different units, markets or varieties, so I cannot compare them.", "इन रिकॉर्ड की इकाई, मंडी या किस्म अलग है; तुलना नहीं कर सकता।", "ದಾಖಲೆಗಳ ಘಟಕ, ಮಾರುಕಟ್ಟೆ ಅಥವಾ ತಳಿ ಬೇರೆ ಇರುವುದರಿಂದ ಹೋಲಿಸಲಾಗುವುದಿಲ್ಲ.")}
        av,bv = [float(r.get("price", r.get("modal_price"))) for r in records]
        sentence = f"{p['commodity']} · {a.get('series') or ''} · {a['market']}: {dates[0]} ₹{amount(av)}, {dates[1]} ₹{amount(bv)} ({a['unit']}). "
        change = amount(abs(av-bv))
        answer = sentence + localize(lang, f"Change: {'up' if av >= bv else 'down'} {change} rupees. Recorded prices, not forecasts.", f"अंतर: {change} रुपये {'बढ़े' if av >= bv else 'घटे'}। ये दर्ज भाव हैं, अनुमान नहीं।", f"ವ್ಯತ್ಯಾಸ: {change} ರೂಪಾಯಿ {'ಏರಿಕೆ' if av >= bv else 'ಇಳಿಕೆ'}. ಇವು ದಾಖಲಾದ ಬೆಲೆಗಳು, ಅಂದಾಜಲ್ಲ.")
        if any("UNVERIFIED" in str(r.get("data_status", "")) or "EXPERIMENTAL" in str(r.get("data_usage", "")) for r in records):
            answer += localize(lang, " Source data is unverified/experimental.", " मूल डेटा अप्रमाणित/प्रायोगिक है।", " ಮೂಲ ಡೇಟಾ ಪರಿಶೀಲಿಸದ/ಪ್ರಾಯೋಗಿಕ ಡೇಟಾ.")
        return {"answer": answer, "records": records, "difference": av-bv}

    def prediction(self, p, lang):
        missing = self.missing(p, lang, "commodity", "market")
        if missing:
            return missing
        crop = "paddy" if p["commodity"] == "rice" else p["commodity"]
        target = date.fromisoformat(p.get("arrival_date") or (date.fromisoformat(p["client_date"]) + timedelta(days=1)).isoformat())
        if target <= date.fromisoformat(p["client_date"]):
            return {"answer": localize(lang, "For a past date, ask for the recorded price. A model estimate is not a historical observation.", "पुरानी तारीख के लिए दर्ज भाव पूछें। मॉडल अनुमान ऐतिहासिक भाव नहीं है।", "ಹಿಂದಿನ ದಿನಾಂಕಕ್ಕೆ ದಾಖಲಾದ ಬೆಲೆ ಕೇಳಿ. ಮಾದರಿ ಅಂದಾಜು ಐತಿಹಾಸಿಕ ದಾಖಲೆಯಲ್ಲ.")}
        if crop in {"tomato", "potato", "paddy", "maize"}:
            # Reuse the same recursive market forecast as the Mandi Price AI page.
            from apps.api.mandi_price_ai import predict_price, _load_combined_df
            session = self.session_factory()
            try:
                rows = crop_rows(session, {**p, "commodity": crop, "arrival_date": None})
                if not rows:
                    return self.no_data(p, lang)
                markets = {r.market_name for r in rows}
                if len(markets) != 1:
                    return self.no_data(p, lang)
                market = rows[0].market_name
            finally:
                session.close()
            df = _load_combined_df()
            selected = df[(df["crop"].str.upper() == crop.upper()) & (df["market"].str.upper() == market.upper())].sort_values("date")
            if selected.empty:
                return self.no_data(p, lang)
            source_date = selected.iloc[-1]["date"].date()
            if (target - source_date).days > 31:
                return {"answer": localize(lang, "The requested forecast is more than 31 days beyond the model's last input. I cannot provide a reliable estimate.", "यह अनुमान मॉडल के अंतिम डेटा से 31 दिन से अधिक आगे है; विश्वसनीय अनुमान उपलब्ध नहीं है।", "ಈ ಅಂದಾಜು ಮಾದರಿಯ ಕೊನೆಯ ಡೇಟಾದಿಂದ 31 ದಿನಗಳಿಗಿಂತ ಮುಂದಿದೆ. ವಿಶ್ವಾಸಾರ್ಹ ಅಂದಾಜು ಲಭ್ಯವಿಲ್ಲ.")}
            price = predict_price(crop, market, target.isoformat())
            if not math.isfinite(price) or price <= 0:
                return self.no_data(p, lang)
            answer = localize(lang,
                f"Market-level ML estimate for {crop} at {market} on {target}: {amount(price)} rupees per quintal. Input date {source_date}. This is a recursive forecast, not an observed price or a variety/grade-specific estimate.",
                f"{target} के लिए {market} में {crop} का मंडी-स्तर मॉडल अनुमान {amount(price)} रुपये प्रति क्विंटल है। मूल डेटा {source_date} का है। यह क्रमिक अनुमान है, दर्ज या किस्म/ग्रेड-विशिष्ट भाव नहीं।",
                f"{target} ರಂದು {market} ನಲ್ಲಿ {crop} ಮಾರುಕಟ್ಟೆ ಮಟ್ಟದ ಮಾದರಿ ಅಂದಾಜು ಪ್ರತಿ ಕ್ವಿಂಟಾಲ್‌ಗೆ {amount(price)} ರೂಪಾಯಿ. ಮೂಲ ಡೇಟಾ {source_date}. ಇದು ಪುನರಾವರ್ತಿತ ಅಂದಾಜು; ದಾಖಲಾದ ಅಥವಾ ತಳಿ/ಗ್ರೇಡ್ ನಿರ್ದಿಷ್ಟ ಬೆಲೆಯಲ್ಲ.")
            answer += localize(lang, " Inputs are from the project's supplied historical dataset.", " मूल डेटा प्रोजेक्ट का दिया गया ऐतिहासिक डेटासेट है।", " ಮೂಲ ಡೇಟಾ ಪ್ರಾಜೆಕ್ಟ್‌ಗೆ ಒದಗಿಸಿದ ಐತಿಹಾಸಿಕ ಡೇಟಾಸೆಟ್.")
            return {"answer": answer, "forecast": {"price": price, "market": market, "commodity": crop, "unit": "INR_PER_QUINTAL", "prediction_date": target.isoformat(), "input_date": source_date.isoformat(), "model": "existing ExtraTrees pipeline", "kind": "recursive_market_estimate"}}
        if crop in ("coffee", "pepper"):
            # Read the actual requested series/market observation; do not invoke
            # the shared baseline which can label a series price with any market.
            record = self.price_lookup({**p, "arrival_date": None})
            if not record or record.get("needs_variety"):
                return {**self.no_data(p, lang), "needs_clarification": True}
            price = record["price"]
            return {"answer": localize(lang,
                f"{crop}, {record.get('series')}, {record['market']}: last-value baseline for {target}, {amount(price)} rupees {record['unit']}. It repeats the observation dated {record['arrival_date']}; it is not a new ML forecast or a live offer.",
                f"{crop}, {record.get('series')}, {record['market']}: {target} का अंतिम-भाव बेसलाइन {amount(price)} रुपये {record['unit']} है। यह {record['arrival_date']} का दर्ज भाव दोहराता है; नया ML पूर्वानुमान या लाइव ऑफर नहीं।",
                f"{crop}, {record.get('series')}, {record['market']}: {target} ಗಾಗಿ ಕೊನೆಯ ಬೆಲೆಯ ಬೇಸ್‌ಲೈನ್ {amount(price)} ರೂಪಾಯಿ {record['unit']}. ಇದು {record['arrival_date']} ರ ಬೆಲೆಯನ್ನು ಪುನರಾವರ್ತಿಸುತ್ತದೆ; ಹೊಸ ML ಅಂದಾಜು ಅಥವಾ ನೇರ ಕೊಡುಗೆಯಲ್ಲ."), "forecast": {**record, "prediction_date": target.isoformat(), "kind": "last_value_baseline"}}
        return self.no_data(p, lang)

    def no_data(self, p, lang):
        detail = f"{p.get('commodity') or ''}, {p.get('variety') or ''}, {p.get('market') or ''}, {p.get('arrival_date') or 'latest recorded'}"
        return {"answer": localize(lang, f"No matching data is available: {detail}. I will not substitute another market, date or benchmark price.", f"मिलता डेटा उपलब्ध नहीं है: {detail}। दूसरी मंडी, तारीख या बेंचमार्क भाव नहीं दूँगा।", f"ಹೊಂದುವ ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ: {detail}. ಬೇರೆ ಮಾರುಕಟ್ಟೆ, ದಿನಾಂಕ ಅಥವಾ ಮಾನದಂಡ ಬೆಲೆಯನ್ನು ಬಳಸುವುದಿಲ್ಲ.")}

    def harvest_route(self, p, lang):
        missing = self.missing(p, lang, "commodity", "origin", "quantity", "quantity_unit")
        if missing:
            return missing
        from apps.api.harvest_routes import HarvestRouteRequest, harvest_routes_payload
        import json
        route_series = p.get("variety")
        if p.get("commodity") in ("tomato", "paddy", "maize", "potato"):
            if not p.get("variety") or not p.get("grade"):
                return {"answer": localize(lang, "Please specify a variety and grade for comparable route prices.", "तुलनीय रूट भाव के लिए किस्म और ग्रेड बताइए।", "ಹೋಲಿಸಬಹುದಾದ ಮಾರ್ಗ ಬೆಲೆಗಾಗಿ ತಳಿ ಮತ್ತು ಗ್ರೇಡ್ ತಿಳಿಸಿ."), "needs_clarification": True}
            route_series = json.dumps([p["variety"], p["grade"]])
        unit = str(p["quantity_unit"]).lower()
        if unit not in ("kg", "quintal"):
            return self.missing({**p, "quantity_unit": None}, lang, "quantity_unit")
        qty = float(p["quantity"]) * (100 if unit == "quintal" else 1)
        payload = HarvestRouteRequest(commodity="paddy" if p["commodity"] == "rice" else p["commodity"], origin=p["origin"], quantity_kg=qty,
            latitude=p.get("latitude"), longitude=p.get("longitude"), series=route_series,
            vehicle_mode=p.get("vehicle_mode", "auto"), vehicle_id=p.get("vehicle_id"), ownership=p.get("ownership", "hired"))
        session = self.session_factory()
        try:
            result = harvest_routes_payload(session, payload)
        finally:
            session.close()
        markets = [m for m in result.get("markets", []) if m.get("net_estimate_inr") is not None]
        if not markets:
            return {"answer": localize(lang, "The route service cannot calculate a net return: road distance or comparable price units are unavailable.", "सड़क दूरी या तुलनीय भाव की इकाई उपलब्ध नहीं है; शुद्ध आय नहीं निकाल सकता।", "ರಸ್ತೆ ದೂರ ಅಥವಾ ಹೋಲಿಸಬಹುದಾದ ಬೆಲೆಯ ಘಟಕ ಲಭ್ಯವಿಲ್ಲ; ನಿವ್ವಳ ಆದಾಯ ಲೆಕ್ಕಿಸಲಾಗುವುದಿಲ್ಲ."), "route": result}
        m = markets[0]
        trade_name = re.sub(r"[ ,;/-]*\b\d{10}\b", "", str(m["market_name"])).strip(" ,;/-")
        answer = localize(lang,
            f"For {amount(qty)} kg of {p['commodity']} from {p['origin']}, {trade_name}: {amount(m['distance_km'])} kilometres, estimated transport {amount(m['transport_estimate_inr'])} rupees, net return {amount(m['net_estimate_inr'])} rupees. Price date {m.get('price_date')}. These are the existing route service's estimates, not guaranteed returns.",
            f"{p['origin']} से {amount(qty)} किलो {p['commodity']} के लिए {trade_name}: दूरी {amount(m['distance_km'])} किलोमीटर, अनुमानित किराया {amount(m['transport_estimate_inr'])} रुपये, शुद्ध आय {amount(m['net_estimate_inr'])} रुपये। भाव तारीख {m.get('price_date')}। ये मौजूदा सेवा के अनुमान हैं, गारंटी नहीं।",
            f"{p['origin']} ನಿಂದ {amount(qty)} ಕೆಜಿ {p['commodity']} ಗೆ {trade_name}: ದೂರ {amount(m['distance_km'])} ಕಿಲೋಮೀಟರ್, ಅಂದಾಜು ಸಾರಿಗೆ {amount(m['transport_estimate_inr'])} ರೂಪಾಯಿ, ನಿವ್ವಳ ಆದಾಯ {amount(m['net_estimate_inr'])} ರೂಪಾಯಿ. ಬೆಲೆ ದಿನಾಂಕ {m.get('price_date')}. ಇವು ಈಗಿರುವ ಸೇವೆಯ ಅಂದಾಜುಗಳು, ಖಾತರಿಯಲ್ಲ.")
        if "UNVERIFIED" in str(result.get("data_status")):
            answer += localize(lang, " Source prices are unverified.", " मूल भाव अप्रमाणित हैं।", " ಮೂಲ ಬೆಲೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿಲ್ಲ.")
        return {"answer": answer, "route": result}

    def market_rankings(self, p, lang):
        if missing := self.missing(p, lang, "commodity"):
            return missing
        crop = p["commodity"]
        session = self.session_factory()
        try:
            if crop in {"paddy", "tomato", "potato", "maize"}:
                rows = crop_rows(session, {**p, "market": None})
                if not rows:
                    return self.no_data(p, lang)
                day = rows[0].market_date
                rows = [r for r in rows if r.market_date == day]
                identities = {(r.variety,r.grade,r.unit) for r in rows}
                if len(identities) != 1:
                    return {"answer": localize(lang, "Please specify a variety and grade to compare like-for-like market prices.", "मंडियों की सही तुलना के लिए किस्म और ग्रेड बताइए।", "ಮಾರುಕಟ್ಟೆ ಬೆಲೆಗಳನ್ನು ಹೋಲಿಸಲು ತಳಿ ಮತ್ತು ಗ್ರೇಡ್ ತಿಳಿಸಿ."), "needs_clarification": True}
                best = max(rows, key=lambda r: r.modal_price)
                record = {"market": best.market_name, "price": float(best.modal_price), "date": day.isoformat(), "unit": best.unit, "variety": best.variety, "data_status": best.data_status}
            else:
                if crop in ("coffee", "pepper") and not p.get("variety"):
                    return self.missing(p, lang, "variety")
                from apps.api.market_rankings import market_rankings_payload
                result = market_rankings_payload(session, crop, p.get("variety"), 5)
                rankings = result.get("rankings", [])
                if not rankings:
                    return self.no_data(p, lang)
                if p.get("arrival_date") and any(r.get("date") != p["arrival_date"] for r in rankings):
                    return self.no_data(p, lang)
                days = {r.get("date") for r in rankings}
                units = {r.get("unit") or result.get("unit") for r in rankings}
                if len(days) != 1 or None in days or len(units) != 1 or None in units:
                    return {"answer": localize(lang, "The market quotations do not share a verified date and unit, so I cannot name a comparable best price.", "भाव की तारीख और इकाई समान नहीं है; सही तुलना उपलब्ध नहीं है।", "ಮಾರುಕಟ್ಟೆ ಬೆಲೆಗಳ ದಿನಾಂಕ ಮತ್ತು ಘಟಕ ಒಂದೇ ಇಲ್ಲ; ಸರಿಯಾದ ಹೋಲಿಕೆ ಲಭ್ಯವಿಲ್ಲ.")}
                top = rankings[0]
                record = {"market": top.get("market_name"), "price": top["price"], "date": top["date"], "unit": next(iter(units)), "variety": result.get("selected_series"), "data_status": result.get("data_status")}
        finally:
            session.close()
        answer = localize(lang,
            f"Highest comparable recorded {crop} price: {record['market']}, {amount(record['price'])} rupees {record['unit']}, dated {record['date']}, variety {record.get('variety')}. This ranks price, before transport costs.",
            f"तुलनीय दर्ज {crop} भाव में सबसे अधिक: {record['market']}, {amount(record['price'])} रुपये {record['unit']}, तारीख {record['date']}, किस्म {record.get('variety')}। इसमें किराया नहीं घटाया गया।",
            f"ಹೋಲಿಸಬಹುದಾದ ದಾಖಲಾದ {crop} ಬೆಲೆಯಲ್ಲಿ ಹೆಚ್ಚು: {record['market']}, {amount(record['price'])} ರೂಪಾಯಿ {record['unit']}, ದಿನಾಂಕ {record['date']}, ತಳಿ {record.get('variety')}. ಇದರಲ್ಲಿ ಸಾರಿಗೆ ವೆಚ್ಚ ಕಳೆದಿಲ್ಲ.")
        if "UNVERIFIED" in str(record.get("data_status")):
            answer += localize(lang, " Source data is unverified.", " मूल डेटा अप्रमाणित है।", " ಮೂಲ ಡೇಟಾ ಪರಿಶೀಲಿಸಿಲ್ಲ.")
        return {"answer": answer, "ranking": record}

    def weather(self, p, lang):
        location = p.get("market") if p.get("explicit_market") else p.get("origin") or p.get("market")
        if not location:
            return self.missing(p, lang, "market")
        from apps.api.weather import weather_payload
        result = weather_payload(location)
        return {"answer": localize(lang,
            f"Current weather at {result['location']}: {result['temperature_c']} degrees Celsius, humidity {result['humidity_percent']} percent. {result['description']}.",
            f"{result['location']} का वर्तमान मौसम: {result['temperature_c']} डिग्री सेल्सियस, नमी {result['humidity_percent']} प्रतिशत। {result['description']}।",
            f"{result['location']} ನಲ್ಲಿ ಈಗಿನ ಹವಾಮಾನ: {result['temperature_c']} ಡಿಗ್ರಿ ಸೆಲ್ಸಿಯಸ್, ತೇವಾಂಶ {result['humidity_percent']} ಪ್ರತಿಶತ. {result['description']}."), "weather": result}

    def cold_storage(self, p, lang):
        from apps.api.cold_storage import location_payload
        location = p.get("market") if p.get("explicit_market") else p.get("origin") or p.get("market")
        if not location:
            return self.missing(p, lang, "origin")
        result = location_payload(location)
        facilities = result.get("facilities", [])
        if not facilities:
            return {"answer": localize(lang, f"No matching cold-storage records for {location}.", f"{location} के लिए शीतगृह रिकॉर्ड नहीं मिले।", f"{location} ಗೆ ಹೊಂದುವ ಶೀತಗೃಹ ದಾಖಲೆ ಸಿಗಲಿಲ್ಲ."), "storage": result}
        f = facilities[0]
        return {"answer": localize(lang,
            f"Near {location}: {f['name']}, {f['location']}. Listed capacity {f.get('capacity_mt')} metric tonnes. This is a facility record; confirm current operation, crop compatibility and available space with the facility.",
            f"{location} के पास: {f['name']}, {f['location']}। दर्ज क्षमता {f.get('capacity_mt')} मीट्रिक टन। वर्तमान संचालन, फसल अनुकूलता और खाली जगह की पुष्टि सुविधा से करें।",
            f"{location} ಹತ್ತಿರ: {f['name']}, {f['location']}. ದಾಖಲಾದ ಸಾಮರ್ಥ್ಯ {f.get('capacity_mt')} ಮೆಟ್ರಿಕ್ ಟನ್. ಪ್ರಸ್ತುತ ಕಾರ್ಯಾಚರಣೆ, ಬೆಳೆ ಹೊಂದಾಣಿಕೆ ಮತ್ತು ಖಾಲಿ ಜಾಗವನ್ನು ಸಂಸ್ಥೆಯೊಂದಿಗೆ ಖಚಿತಪಡಿಸಿ."), "storage": result}

    def recommendation(self, p, lang):
        return {"answer": localize(lang, "No connected service provides a verified SELL, WAIT or STORE decision. I can read recorded prices, existing forecasts, route net returns and storage records to help you compare options.", "कोई जुड़ी सेवा सत्यापित SELL, WAIT या STORE सलाह नहीं देती। विकल्पों की तुलना के लिए दर्ज भाव, अनुमान, शुद्ध आय और शीतगृह रिकॉर्ड बता सकता हूँ।", "ಸಂಪರ್ಕಿತ ಸೇವೆಯಲ್ಲಿ ಪರಿಶೀಲಿಸಿದ SELL, WAIT ಅಥವಾ STORE ಸಲಹೆ ಲಭ್ಯವಿಲ್ಲ. ಆಯ್ಕೆ ಹೋಲಿಸಲು ದಾಖಲಾದ ಬೆಲೆ, ಅಂದಾಜು, ನಿವ್ವಳ ಆದಾಯ ಮತ್ತು ಶೀತಗೃಹ ದಾಖಲೆ ಹೇಳಬಹುದು.")}

    def my_crops(self, p, lang):
        from sqlalchemy import select
        from cropmandi.db.models import FarmerCrop
        session = self.session_factory()
        try:
            # Existing app uses a shared demo inventory; do not imply tenant auth.
            rows = session.scalars(select(FarmerCrop)).all()
            if p.get("commodity"):
                code = "paddy" if p["commodity"] == "rice" else p["commodity"]
                rows = [r for r in rows if r.commodity == code]
            items = [f"{r.commodity}, {r.variety}, {amount(r.quantity)} {r.unit}, {r.location}" for r in rows[:5]]
        finally:
            session.close()
        return {"answer": localize(lang, "Existing app inventory: ", "ऐप में दर्ज फसलें: ", "ಅಪ್ಲಿಕೇಶನ್‌ನಲ್ಲಿ ದಾಖಲಾದ ಬೆಳೆಗಳು: ") + ("; ".join(items) or localize(lang, "No crops found.", "कोई फसल नहीं मिली।", "ಬೆಳೆಗಳು ಸಿಗಲಿಲ್ಲ.")), "inventory_count": len(rows)}
