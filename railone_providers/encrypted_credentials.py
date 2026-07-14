"""M-PESA credential provider backed by RailOne's encrypted vault."""

from __future__ import annotations

from collections.abc import Mapping

from railone_security import EncryptedProviderCredentialVault

from .mpesa import MpesaCredentials


class EncryptedMpesaCredentialProvider:
    provider_id = "MPESA-KE"

    def __init__(
        self, vault: EncryptedProviderCredentialVault,
        *, credential_references: Mapping[str, str] | None = None,
    ) -> None:
        self._vault = vault
        defaults = {
            "consumer_key": "consumer_key",
            "consumer_secret": "consumer_secret",
            "initiator_name": "initiator_name",
            "security_credential": "security_credential",
            "business_shortcode": "business_shortcode",
        }
        self._references = {**defaults, **dict(credential_references or {})}
        if set(self._references) != set(defaults):
            raise ValueError("M-PESA credential reference mapping is invalid")

    def get(self) -> MpesaCredentials:
        value = lambda field: self._vault.resolve(
            provider_id=self.provider_id,
            credential_name=self._references[field],
        )
        return MpesaCredentials(
            consumer_key=value("consumer_key"),
            consumer_secret=value("consumer_secret"),
            initiator_name=value("initiator_name"),
            security_credential=value("security_credential"),
            business_shortcode=value("business_shortcode"),
        )
