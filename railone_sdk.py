# ==============================
# railone_sdk.py (FIXED)
# ==============================

import requests
import time
import uuid
import hmac
import hashlib
import random
import json
from typing import Optional, Dict, Any


class RailOneClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.api_secret = api_secret
        self.max_retries = max_retries

    # --------------------------------
    # SIGN REQUEST
    # --------------------------------
    def _sign(self, payload: Dict[str, Any]) -> str:
        if not self.api_secret:
            return ""

        payload_str = json.dumps(payload, sort_keys=True) if payload else ""

        return hmac.new(
            self.api_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

    # --------------------------------
    # BACKOFF
    # --------------------------------
    def _sleep(self, attempt: int):
        base = 2 ** attempt
        jitter = random.uniform(0, 1)
        time.sleep(base + jitter)

    # --------------------------------
    # REQUEST CORE
    # --------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None
    ):
        url = f"{self.base_url}{path}"

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # --------------------------------
        # IDEMPOTENCY
        # --------------------------------
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        headers["Idempotency-Key"] = idempotency_key

        # --------------------------------
        # SIGNATURE
        # --------------------------------
        signature = self._sign(payload or {})

        if signature:
            headers["X-RailOne-Signature"] = signature

        # --------------------------------
        # RETRY LOOP
        # --------------------------------
        for attempt in range(self.max_retries):

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )

                if response.status_code >= 500:
                    raise Exception(f"Server error {response.status_code}")

                response.raise_for_status()
                return response.json()

            except Exception as e:
                print(f"⚠️ Request failed (attempt {attempt+1}): {str(e)}")

                if attempt == self.max_retries - 1:
                    raise

                self._sleep(attempt)

    # --------------------------------
    # TRANSFER
    # --------------------------------
    def transfer(
        self,
        payload: Dict[str, Any],
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ):
        data = payload.copy()

        if webhook_url:
            data["webhook_url"] = webhook_url

        return self._request(
            "POST",
            "/v1/transfers",
            data,
            idempotency_key
        )

    # --------------------------------
    # STATUS
    # --------------------------------
    def get_status(self, tx_id: str):
        return self._request(
            "GET",
            f"/v1/transactions/{tx_id}"
        )

    # --------------------------------
    # QUOTE
    # --------------------------------
    def quote(self, payload: Dict[str, Any]):
        return self._request(
            "POST",
            "/v1/quote",
            payload
        )

    # --------------------------------
    # ONBOARD
    # --------------------------------
    def onboard(self, payload: Dict[str, Any]):
        return self._request(
            "POST",
            "/v1/onboard",
            payload
        )