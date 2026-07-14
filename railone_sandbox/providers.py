from __future__ import annotations

from railone_operations import ProviderExecutionRequest, ProviderSubmissionResult

from .effects import SandboxEffectBroker


class SandboxBankAdapter:
    provider_id = "BANK-KE"
    supports_idempotency = True

    def __init__(self, broker: SandboxEffectBroker) -> None:
        self._broker = broker

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        if request.provider_id != self.provider_id:
            raise ValueError("bank simulator received another provider's request")
        if request.currency_from != "KES" or request.currency_to != "KES":
            raise ValueError("domestic bank simulator supports KES only")
        if request.rail not in {"DOMESTIC_BANK", "PESALINK", "RTGS"}:
            raise ValueError("domestic bank simulator received an unsupported rail")
        if request.amount_minor != request.receive_amount_minor:
            raise ValueError("domestic bank simulator requires equal KES amounts")
        return self._broker.submit(request)


class SandboxMpesaAdapter:
    provider_id = "MPESA-KE"
    # Preserve the production Daraja B2C uncertainty boundary.
    supports_idempotency = False

    def __init__(self, broker: SandboxEffectBroker) -> None:
        self._broker = broker

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        if request.provider_id != self.provider_id:
            raise ValueError("M-PESA simulator received another provider's request")
        if request.rail != "MOBILE_MONEY":
            raise ValueError("M-PESA simulator requires MOBILE_MONEY rail")
        return self._broker.submit(request)
