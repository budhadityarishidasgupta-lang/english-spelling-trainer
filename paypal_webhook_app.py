"""Lightweight FastAPI app to handle PayPal webhooks (Option B).

This app verifies PayPal webhook signatures using PayPal's REST API and
records successful payments in the ``spelling_payments`` table. It is designed
as a standalone service so it can be deployed separately from the Streamlit
apps.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shared.db import engine
from spelling_app.utils.paypal_verify import _get_access_token, _get_base_url

app = FastAPI(title="WordSprint PayPal Webhook")

PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
PAYPAL_BUTTON_ID = os.getenv("PAYPAL_BUTTON_ID", "UNKNOWN")


class WebhookVerificationError(Exception):
    """Raised when PayPal webhook signature verification fails."""


async def _get_request_body(request: Request) -> Dict[str, Any]:
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return {}
        return json.loads(body_bytes)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc


async def _verify_paypal_webhook(
    request: Request,
    paypal_transmission_id: str | None,
    paypal_transmission_time: str | None,
    paypal_cert_url: str | None,
    paypal_auth_algo: str | None,
    paypal_transmission_sig: str | None,
) -> Dict[str, Any]:
    """Verify PayPal webhook signature via PayPal's validation API.

    Raises ``WebhookVerificationError`` if verification fails.
    """

    if not PAYPAL_WEBHOOK_ID:
        raise HTTPException(
            status_code=500,
            detail="PAYPAL_WEBHOOK_ID is not configured",
        )

    event_body = await _get_request_body(request)

    # Validate required headers are present
    required_headers = {
        "paypal-transmission-id": paypal_transmission_id,
        "paypal-transmission-time": paypal_transmission_time,
        "paypal-cert-url": paypal_cert_url,
        "paypal-auth-algo": paypal_auth_algo,
        "paypal-transmission-sig": paypal_transmission_sig,
    }
    missing = [h for h, v in required_headers.items() if not v]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing PayPal webhook headers: {', '.join(missing)}",
        )

    verification_payload = {
        "auth_algo": paypal_auth_algo,
        "cert_url": paypal_cert_url,
        "transmission_id": paypal_transmission_id,
        "transmission_sig": paypal_transmission_sig,
        "transmission_time": paypal_transmission_time,
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event_body,
    }

    access_token = _get_access_token()
    base_url = _get_base_url()
    verify_url = f"{base_url}/v1/notifications/verify-webhook-signature"

    response = requests.post(
        verify_url,
        json=verification_payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not response.ok:
        raise WebhookVerificationError(
            f"PayPal verification HTTP {response.status_code}: {response.text}"
        )

    verification_data = response.json()
    if verification_data.get("verification_status") != "SUCCESS":
        raise WebhookVerificationError(
            f"PayPal verification failed: {verification_data.get('verification_status')}"
        )

    return event_body


def _extract_payment_details(event_body: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Pull out payment id, email, button id and status from a webhook payload."""
    resource = event_body.get("resource", {}) or {}

    payer_email = (
        resource.get("payer", {}).get("email_address")
        or resource.get("payment_source", {})
        .get("paypal", {})
        .get("email_address")
    )
    payment_id = resource.get("id")
    custom_id = resource.get("custom_id") or resource.get("supplementary_data", {}).get(
        "related_ids", {}
    ).get("order_id")
    status = resource.get("status") or event_body.get("event_type")

    return {
        "payer_email": payer_email,
        "payment_id": payment_id,
        "button_id": custom_id or PAYPAL_BUTTON_ID,
        "status": status,
    }


def _record_payment(details: Dict[str, Optional[str]]) -> None:
    if not details.get("payment_id"):
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO spelling_payments (user_email, paypal_payment_id, paypal_button_id, status, paid_at)
                VALUES (:email, :pid, :bid, :status, CURRENT_TIMESTAMP)
                ON CONFLICT (paypal_payment_id) DO NOTHING
                """
            ),
            {
                "email": details.get("payer_email") or "unknown",
                "pid": details.get("payment_id"),
                "bid": details.get("button_id") or PAYPAL_BUTTON_ID,
                "status": details.get("status") or "UNKNOWN",
            },
        )


@app.get("/")
async def healthcheck():
    return {"status": "ok"}


@app.post("/webhooks/paypal")
async def paypal_webhook(
    request: Request,
    paypal_transmission_id: str | None = Header(None, convert_underscores=False),
    paypal_transmission_time: str | None = Header(None, convert_underscores=False),
    paypal_cert_url: str | None = Header(None, convert_underscores=False),
    paypal_auth_algo: str | None = Header(None, convert_underscores=False),
    paypal_transmission_sig: str | None = Header(None, convert_underscores=False),
):
    try:
        event_body = await _verify_paypal_webhook(
            request,
            paypal_transmission_id,
            paypal_transmission_time,
            paypal_cert_url,
            paypal_auth_algo,
            paypal_transmission_sig,
        )
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    details = _extract_payment_details(event_body)
    _record_payment(details)

    return JSONResponse({"status": "processed", "payment_id": details.get("payment_id")})


if __name__ == "__main__":  # pragma: no cover - convenience
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("paypal_webhook_app:app", host="0.0.0.0", port=port, reload=True)
