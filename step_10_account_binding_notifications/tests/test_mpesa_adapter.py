from __future__ import annotations

import json
import unittest

from railone_operations import (
    ProviderExecutionRequest,
    ProviderOutcome,
    RejectionDisposition,
)
from railone_providers import (
    HttpResponse,
    MpesaB2CAdapter,
    MpesaConfig,
    MpesaCredentials,
)


class FixedCredentials:
    def __init__(self) -> None:
        self.value = MpesaCredentials(
            consumer_key="consumer-key",
            consumer_secret="consumer-secret",
            initiator_name="railone-sandbox",
            security_credential="encrypted-initiator-credential",
            business_shortcode="600000",
        )

    def get(self) -> MpesaCredentials:
        return self.value


class FakeTransport:
    def __init__(self, *responses: HttpResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs) -> HttpResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected provider transport call")
        return self.responses.pop(0)


def request(**overrides) -> ProviderExecutionRequest:
    values = {
        "idempotency_key": "R1IDEM-STABLE-001",
        "request_sha256": "a" * 64,
        "utt_id": "UTT-001",
        "rtt_id": "RTT-001",
        "attempt_number": 1,
        "provider_id": "MPESA-KE",
        "rail": "MOBILE_MONEY",
        "amount_minor": 250_000,
        "currency_from": "KES",
        "receive_amount_minor": 250_000,
        "currency_to": "KES",
        "payer_account_reference": "PAYER-PRIVATE-REFERENCE",
        "beneficiary_account_reference": "254712345678",
    }
    values.update(overrides)
    return ProviderExecutionRequest(**values)


def adapter(transport: FakeTransport) -> MpesaB2CAdapter:
    return MpesaB2CAdapter(
        config=MpesaConfig(
            result_url="https://callbacks.railone.example/mpesa/result",
            timeout_url="https://callbacks.railone.example/mpesa/timeout",
        ),
        credentials=FixedCredentials(),
        transport=transport,
    )


class MpesaAdapterTests(unittest.TestCase):
    def test_b2c_acceptance_is_processing_only_and_keeps_correlation_context(self) -> None:
        transport = FakeTransport(
            HttpResponse(200, b'{"access_token":"token","expires_in":"3599"}'),
            HttpResponse(
                200,
                b'{"ResponseCode":"0","ConversationID":"AG_001",'
                b'"OriginatorConversationID":"R1_ORIGIN_001"}',
            ),
        )

        result = adapter(transport).submit(request())

        self.assertEqual(result.outcome, ProviderOutcome.ACCEPTED)
        self.assertEqual(result.external_reference, "AG_001")
        self.assertEqual(
            dict(result.provider_context)["originator_conversation_id"],
            "R1_ORIGIN_001",
        )
        self.assertEqual(dict(result.provider_context)["amount_minor"], "250000")
        self.assertFalse(MpesaB2CAdapter.supports_idempotency)
        body = json.loads(transport.calls[1]["body"])
        self.assertEqual(body["Amount"], 2500)
        self.assertEqual(body["PartyB"], "254712345678")
        self.assertEqual(body["Occasion"], "R1IDEM-STABLE-001")
        self.assertNotIn("PAYER-PRIVATE-REFERENCE", repr(body))

    def test_oauth_failure_is_retryable_because_payment_endpoint_was_not_called(self) -> None:
        transport = FakeTransport(HttpResponse(503, b'{"error":"unavailable"}'))

        result = adapter(transport).submit(request())

        self.assertEqual(result.outcome, ProviderOutcome.REJECTED)
        self.assertEqual(result.rejection_disposition, RejectionDisposition.RETRYABLE)
        self.assertEqual(result.code, "MPESA_AUTH_UNAVAILABLE")
        self.assertEqual(len(transport.calls), 1)

    def test_unparseable_payment_response_is_an_unknown_outcome(self) -> None:
        transport = FakeTransport(
            HttpResponse(200, b'{"access_token":"token","expires_in":3599}'),
            HttpResponse(502, b"not-json"),
        )

        result = adapter(transport).submit(request())

        self.assertEqual(result.outcome, ProviderOutcome.UNKNOWN)
        self.assertEqual(result.code, "MPESA_RESPONSE_UNPARSEABLE")

    def test_invalid_msisdn_and_fractional_kes_are_rejected_before_network(self) -> None:
        transport = FakeTransport()
        mpesa = adapter(transport)

        invalid_msisdn = mpesa.submit(
            request(beneficiary_account_reference="0712345678")
        )
        fractional = mpesa.submit(
            request(amount_minor=250_001, receive_amount_minor=250_001)
        )

        self.assertEqual(invalid_msisdn.code, "MPESA_BENEFICIARY_MSISDN_INVALID")
        self.assertEqual(fractional.code, "MPESA_WHOLE_KES_REQUIRED")
        self.assertEqual(transport.calls, [])

    def test_credentials_do_not_leak_in_repr(self) -> None:
        credentials = FixedCredentials().value
        rendered = repr(credentials)

        self.assertNotIn("consumer-key", rendered)
        self.assertNotIn("consumer-secret", rendered)
        self.assertNotIn("encrypted-initiator-credential", rendered)


if __name__ == "__main__":
    unittest.main()
