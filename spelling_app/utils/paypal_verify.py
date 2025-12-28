"""Utility helpers for verifying PayPal order or capture IDs via the PayPal API."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


PAYPAL_TIMEOUT = 15


def _get_base_url() -> str:
    """Return the PayPal API base URL depending on environment configuration."""
    env = os.getenv("PAYPAL_ENV", "live").lower()
    if env == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


def _get_access_token() -> str:
    """Retrieve an OAuth access token from PayPal."""
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("PayPal credentials are not configured")

    token_url = f"{_get_base_url()}/v1/oauth2/token"
    response = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=PAYPAL_TIMEOUT,
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("PayPal access token missing in response")
    return access_token


def _is_order_completed(order_data: Dict[str, Any]) -> bool:
    """Determine if an order payload is completed, including capture checks."""
    if order_data.get("status") == "COMPLETED":
        return True

    purchase_units = order_data.get("purchase_units", []) or []
    for unit in purchase_units:
        payments = unit.get("payments", {}) or {}
        captures = payments.get("captures", []) or []
        for capture in captures:
            if capture.get("status") == "COMPLETED":
                return True
    return False


def _make_authorized_get(url: str, access_token: str) -> requests.Response:
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=PAYPAL_TIMEOUT,
    )


def verify_paypal_payment_id(pasted_id: str) -> Dict[str, Any]:
    """
    Verify a PayPal order or capture ID.

    Args:
        pasted_id: The PayPal ID supplied by the client.

    Returns:
        dict: {"verified": bool, "status": str, "id": str, "kind": "order|capture|unknown"}
    """

    def _default_response(kind: str = "unknown", status: str = "UNKNOWN") -> Dict[str, Any]:
        return {"verified": False, "status": status, "id": pasted_id, "kind": kind}

    if not pasted_id:
        return _default_response(status="EMPTY_ID")

    try:
        access_token = _get_access_token()
        base_url = _get_base_url()

        # Try order endpoint first
        order_url = f"{base_url}/v2/checkout/orders/{pasted_id}"
        order_response = _make_authorized_get(order_url, access_token)
        if order_response.ok:
            order_data = order_response.json()
            status = order_data.get("status", "UNKNOWN")
            if _is_order_completed(order_data):
                return {"verified": True, "status": status, "id": order_data.get("id", pasted_id), "kind": "order"}
            return _default_response(kind="order", status=status)

        # Fallback to capture endpoint
        capture_url = f"{base_url}/v2/payments/captures/{pasted_id}"
        capture_response = _make_authorized_get(capture_url, access_token)
        if capture_response.ok:
            capture_data = capture_response.json()
            status = capture_data.get("status", "UNKNOWN")
            if status == "COMPLETED":
                return {"verified": True, "status": status, "id": capture_data.get("id", pasted_id), "kind": "capture"}
            return _default_response(kind="capture", status=status)

        return _default_response(status=f"HTTP_{capture_response.status_code}")
    except Exception:
        return _default_response(status="ERROR")
