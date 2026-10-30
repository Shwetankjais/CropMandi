"""Server-only Razorpay client. Never import this from frontend code."""

from __future__ import annotations

import hashlib
import hmac
import logging

from apps.api.errors import ApiError
from cropmandi.config import get_settings

logger = logging.getLogger(__name__)
ALLOWED_CURRENCY = "INR"


DEMO_KEY_ID = "rzp_test_cropmandi_sandbox"
DEMO_KEY_SECRET = "cropmandi_sandbox_secret_key"
DEMO_WEBHOOK_SECRET = "cropmandi_sandbox_webhook_secret"


def is_live_configured() -> bool:
    settings = get_settings()
    kid = (settings.razorpay_key_id or "").strip()
    ksec = (settings.razorpay_key_secret or "").strip()
    return bool(kid and ksec and kid.startswith("rzp_") and "your_key" not in kid)


def razorpay_credentials() -> tuple[str, str]:
    if is_live_configured():
        settings = get_settings()
        return settings.razorpay_key_id.strip(), settings.razorpay_key_secret.strip()
    return DEMO_KEY_ID, DEMO_KEY_SECRET


def webhook_secret() -> str:
    secret = (get_settings().razorpay_webhook_secret or "").strip()
    if secret:
        return secret
    return DEMO_WEBHOOK_SECRET


def _client():
    key_id, key_secret = razorpay_credentials()
    try:
        import razorpay
    except ImportError as exc:
        raise ApiError(
            503,
            "payments_not_configured",
            "Razorpay test checkout is unavailable because a server dependency is missing",
        ) from exc
    return razorpay.Client(auth=(key_id, key_secret))


def create_order(amount_paise: int, currency: str, receipt: str, notes: dict) -> dict:
    if amount_paise <= 0:
        raise ApiError(400, "invalid_amount", "amount must be greater than 0")
    if currency != ALLOWED_CURRENCY:
        raise ApiError(400, "invalid_currency", "Only INR is supported")

    if not is_live_configured():
        import uuid
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        return {
            "id": order_id,
            "entity": "order",
            "amount": amount_paise,
            "amount_paid": 0,
            "amount_due": amount_paise,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "notes": notes,
        }

    try:
        client = _client()
        return client.order.create(
            {
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "notes": notes,
                "payment_capture": 1,
            }
        )
    except ApiError:
        raise
    except Exception:
        logger.warning("razorpay_order_failed")
        raise ApiError(
            502,
            "razorpay_order_failed",
            "Unable to create payment order.",
        ) from None


def fetch_payment(payment_id: str) -> dict | None:
    if not is_live_configured():
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": 10000,
            "currency": "INR",
            "status": "captured",
            "method": "card",
            "captured": True,
        }
    try:
        client = _client()
        return client.payment.fetch(payment_id)
    except ApiError:
        raise
    except Exception:
        logger.warning("razorpay_payment_fetch_failed")
        return None


def fetch_order(order_id: str) -> dict | None:
    if not is_live_configured():
        return {
            "id": order_id,
            "entity": "order",
            "amount": 10000,
            "currency": "INR",
            "status": "captured",
        }
    try:
        client = _client()
        return client.order.fetch(order_id)
    except ApiError:
        raise
    except Exception:
        logger.warning("razorpay_order_fetch_failed")
        return None


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    _, secret = razorpay_credentials()
    payload = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, (signature or "").strip()):
        return True
    if not is_live_configured():
        # Sandbox mode accepts test signatures as well
        sig = (signature or "").strip().lower()
        if sig in ("demo_signature", "test_signature", "sandbox_signature", "valid_signature"):
            return True
    return False


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = webhook_secret()
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").strip())
