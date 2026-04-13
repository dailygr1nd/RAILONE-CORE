import requests


class RailOneClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def transfer(self, payload: dict):
        response = requests.post(
            f"{self.base_url}/v1/transfers",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def investigate_utt(self, utt: str):
        response = requests.get(
            f"{self.base_url}/v1/investigate/utt/{utt}",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def investigate_rtt(self, rtt: str):
        response = requests.get(
            f"{self.base_url}/v1/investigate/rtt/{rtt}",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
