# ==========================================
# provider/mock_adapter.py
# ==========================================

import uuid
import random


class MockAdapter:

    def execute(
        self,
        execution
    ):

        success = random.random() < 0.90

        return {

            "success":
                success,

            "provider_reference":
                f"MOCK-"
                f"{uuid.uuid4().hex[:12]}"
        }

    def query_status(

        self,
        provider_reference
    ):

        return {

            "status":
                "SETTLED"
        }

    def reverse(

        self,
        provider_reference
    ):

        return {

            "success":
                True
        }