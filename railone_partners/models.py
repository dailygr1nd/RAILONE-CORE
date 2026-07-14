"""Partner-institution and opaque account-binding contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from railone_contracts.models import AccountRole, AccountType


def _text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


class InstitutionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    OFFBOARDED = "OFFBOARDED"


class AccountBindingStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True, slots=True)
class PartnerInstitution:
    institution_id: str
    display_name: str
    country_codes: tuple[str, ...]
    currencies: tuple[str, ...]
    supported_roles: tuple[AccountRole, ...]
    status: InstitutionStatus = InstitutionStatus.ACTIVE

    def normalized(self) -> "PartnerInstitution":
        _text("institution_id", self.institution_id)
        _text("display_name", self.display_name)
        if not self.country_codes or not self.currencies or not self.supported_roles:
            raise ValueError("partner institution coverage cannot be empty")
        if len(set(self.country_codes)) != len(self.country_codes):
            raise ValueError("partner country coverage contains duplicates")
        if len(set(self.currencies)) != len(self.currencies):
            raise ValueError("partner currency coverage contains duplicates")
        return self


@dataclass(frozen=True, slots=True)
class AccountBinding:
    account_binding_id: str
    actor_id: str
    institution_id: str
    role: AccountRole
    account_type: AccountType
    currency: str
    display_hint: str
    contact_binding_id: str
    attestation_reference: str
    status: AccountBindingStatus = AccountBindingStatus.ACTIVE

    def normalized(self) -> "AccountBinding":
        for name in (
            "account_binding_id", "actor_id", "institution_id", "currency",
            "display_hint", "contact_binding_id", "attestation_reference",
        ):
            _text(name, getattr(self, name))
        if len(self.display_hint) > 32:
            raise ValueError("account display hint exceeds 32 characters")
        return self
