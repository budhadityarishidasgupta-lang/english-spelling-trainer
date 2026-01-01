from fastapi import FastAPI, Request, HTTPException
from sqlalchemy import text
from shared.db import engine
from spelling_app.repository.registration_repo import (
    mark_registration_verified_by_token,
)
import datetime
import os
import requests
import json

app = FastAPI()

PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
PAYPAL_VERIFY_URL = "https://api.paypal.com/v1/notifications/verify-webhook-signature"


def verify_paypal_signature(headers: dict, body: dict) -> bool:
    """
    Verifies PayPal webhook signature using PayPal API
    """
    auth = (os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET"))

    payload = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": body,
    }

    response = requests.post(
        PAYPAL_VERIFY_URL,
        auth=auth,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=10,
    )

    if response.status_code != 200:
        return False

    verification_status = response.json().get("verification_status")
    return verification_status == "SUCCESS"


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    body = await request.json()
    headers = request.headers

    # 🔐 Verify signature
    if not verify_paypal_signature(headers, body):
        raise HTTPException(status_code=400, detail="Invalid PayPal signature")

    event_type = body.get("event_type")
    resource = body.get("resource", {})

    if event_type != "PAYMENT.CAPTURE.COMPLETED":
        return {"status": "ignored"}

    capture_id = resource.get("id")
    registration_token = resource.get("custom_id")
    amount_info = resource.get("amount", {})
    amount = amount_info.get("value")
    currency = amount_info.get("currency_code")
    status = resource.get("status")

    if not capture_id or status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Invalid payment payload")

    if not registration_token:
        print("[paypal_webhook] Missing registration token; ignoring payment")
        return {"status": "ignored", "reason": "missing_token"}

    with engine.begin() as conn:
        # Store payment
        conn.execute(
            text("""
                INSERT INTO spelling_payments
                (paypal_capture_id, amount, currency, status, received_at)
                VALUES (:capture_id, :amount, :currency, :status, :received_at)
                ON CONFLICT (paypal_capture_id) DO NOTHING
            """),
            {
                "capture_id": capture_id,
                "amount": amount,
                "currency": currency,
                "status": status,
                "received_at": datetime.datetime.utcnow(),
            }
        )


    matched = mark_registration_verified_by_token(registration_token)
    if not matched:
        print(
            f"[paypal_webhook] Registration token not found or already processed: {registration_token}"
        )

    return {"status": "verified"}
