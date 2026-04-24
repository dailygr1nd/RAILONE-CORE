# ==============================
# railone_sdk.py
# ==============================

import requests
from typing import Optional, Dict, Any


class RailOneClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    # --------------------------------
    # INTERNAL REQUEST HANDLER
    # --------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None
    ):
        url = f"{self.base_url}{path}"

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.request(
            method=method,
            url=url,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )

        response.raise_for_status()
        return response.json()

    # --------------------------------
    # TRANSFER
    # --------------------------------
    def transfer(
        self,
        payload: Dict[str, Any],
        webhook_url: Optional[str] = None
    ):
        data = payload.copy()

        if webhook_url:
            data["webhook_url"] = webhook_url

        return self._request(
            "POST",
            "/v1/transfers",
            data
        )

    # --------------------------------
    # GET TRANSACTION STATUS
    # --------------------------------
    def get_status(self, tx_id: str):
        return self._request(
            "GET",
            f"/v1/transactions/{tx_id}"
        )

    # --------------------------------
    # GET TRANSFER (alias for clarity)
    # --------------------------------
    def get_transfer(self, tx_id: str):
        return self.get_status(tx_id)

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
    # ONBOARD USER
    # --------------------------------
    def onboard(self, payload: Dict[str, Any]):
        return self._request(
            "POST",
            "/v1/onboard",
            payload
        )

    # --------------------------------
    # INVESTIGATIONS (optional expansion)
    # --------------------------------
    def investigate_utt(self, utt: str):
        return self._request(
            "GET",
            f"/v1/investigate/utt/{utt}"
        )

    def investigate_rtt(self, rtt: str):
        return self._request(
            "GET",
            f"/v1/investigate/rtt/{rtt}"
        )