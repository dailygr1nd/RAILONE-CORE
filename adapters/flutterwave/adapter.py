import requests

from adapters.base.adapter_contract import (
    RailOneAdapter
)

from .webhook_handler import (
    normalize_flutterwave_webhook
)


class FlutterwaveAdapter(RailOneAdapter):

    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, secret_key):

        self.secret_key = secret_key

        self.headers = {
            "Authorization":
                f"Bearer {secret_key}",

            "Content-Type":
                "application/json"
        }

    def initiate_execution(self, payload):

        endpoint = (
            f"{self.BASE_URL}/payments"
        )

        response = requests.post(
            endpoint,
            json=payload,
            headers=self.headers
        )

        return response.json()

    def query_execution_state(self, execution_id):

        endpoint = (
            f"{self.BASE_URL}/transactions/"
            f"{execution_id}/verify"
        )

        response = requests.get(
            endpoint,
            headers=self.headers
        )

        return response.json()

    def verify_execution(self, payload):

        return normalize_flutterwave_webhook(
            payload
        )

    def reconcile_execution(self, execution_id):

        return self.query_execution_state(
            execution_id
        )

    def recover_execution(self, execution_id):

        return {
            "execution_id": execution_id,
            "recovery_state":
                "provider_requery_required"
        }

    def normalize_webhook(self, payload):

        return normalize_flutterwave_webhook(
            payload
        )