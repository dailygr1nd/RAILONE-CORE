import requests


class RailOneClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    # ------------------------
    # TRANSFER
    # ------------------------
    def transfer(self, payload: dict):
        r = requests.post(
            f"{self.base_url}/v1/transfers",
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    # ------------------------
    # STATUS
    # ------------------------
    def get_transfer(self, utt: str):
        r = requests.get(
            f"{self.base_url}/v1/transfers/{utt}",
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    # ------------------------
    # QUOTE
    # ------------------------
    def quote(self, payload: dict):
        r = requests.post(
            f"{self.base_url}/v1/quote",
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    # ------------------------
    # ONBOARD
    # ------------------------
    def onboard(self, payload: dict):
        r = requests.post(
            f"{self.base_url}/v1/onboard",
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    
    def get_status(self, tx_id: str):
        response = requests.get(
        f"{self.base_url}/v1/transactions/{tx_id}",
        timeout=30
    )
        response.raise_for_status()
        return response.json()