"""Strict commercial contract inputs for quotes and UTTs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

def require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def require_minor_units(name: str, value: int, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {qualifier}")
    return value


class ContextType(StrEnum):
    P2P = "P2P"
    MERCHANT = "MERCHANT"
    PARTNER = "PARTNER"


class PaymentPurpose(StrEnum):
    PERSON_TO_PERSON = "PERSON_TO_PERSON"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    BRANCH_FUND_TRANSFER = "BRANCH_FUND_TRANSFER"
    MERCHANT_TO_MERCHANT = "MERCHANT_TO_MERCHANT"
    REFUND = "REFUND"
    EXPENSE_SETTLEMENT = "EXPENSE_SETTLEMENT"
    BULK_DISBURSEMENT = "BULK_DISBURSEMENT"


class AccountRole(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountType(StrEnum):
    BANK_ACCOUNT = "BANK_ACCOUNT"
    MOBILE_MONEY = "MOBILE_MONEY"
    WALLET = "WALLET"
    CARD_ACCOUNT = "CARD_ACCOUNT"


@dataclass(frozen=True, slots=True)
class AccountEndpoint:
    institution_id: str
    institution_display_name: str
    account_binding_id: str
    role: AccountRole
    account_type: AccountType
    display_hint: str
    contact_binding_id: str
    attestation_reference: str

    def to_payload(self) -> dict[str, str]:
        return {
            "institution_id": require_text("institution_id", self.institution_id),
            "institution_display_name": require_text(
                "institution_display_name", self.institution_display_name
            )[:48],
            "account_binding_id": require_text(
                "account_binding_id", self.account_binding_id
            ),
            "role": self.role.value,
            "account_type": self.account_type.value,
            "display_hint": require_text("display_hint", self.display_hint)[:32],
            "contact_binding_id": require_text(
                "contact_binding_id", self.contact_binding_id
            ),
            "attestation_reference": require_text(
                "attestation_reference", self.attestation_reference
            ),
        }

    @classmethod
    def from_payload(cls, value: Mapping[str, Any]) -> "AccountEndpoint":
        try:
            return cls(
                institution_id=str(value["institution_id"]),
                institution_display_name=str(value["institution_display_name"]),
                account_binding_id=str(value["account_binding_id"]),
                role=AccountRole(value["role"]),
                account_type=AccountType(value["account_type"]),
                display_hint=str(value["display_hint"]),
                contact_binding_id=str(value["contact_binding_id"]),
                attestation_reference=str(value["attestation_reference"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid account endpoint snapshot") from exc


@dataclass(frozen=True, slots=True)
class ActorReference:
    actor_type: str
    actor_id: str
    endpoint: AccountEndpoint
    display_name: str | None = None

    def to_payload(self) -> dict[str, Any]:
        display = self.display_name or require_text("actor_type", self.actor_type).title()
        return {
            "actor_type": require_text("actor_type", self.actor_type).upper(),
            "actor_id": require_text("actor_id", self.actor_id),
            "display_name": require_text("display_name", display)[:48],
            "endpoint": self.endpoint.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class OriginContext:
    origin_system: str
    origin_intent_id: str
    context_type: ContextType
    purpose: PaymentPurpose
    continuity_uid: str | None = None
    merchant_id: str | None = None
    branch_id: str | None = None
    partner_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        if self.context_type is ContextType.MERCHANT and not self.merchant_id:
            raise ValueError("merchant_id is required for merchant context")
        if self.context_type is ContextType.PARTNER and not self.partner_id:
            raise ValueError("partner_id is required for partner context")
        if self.context_type is ContextType.P2P and self.purpose is not PaymentPurpose.PERSON_TO_PERSON:
            raise ValueError("P2P context requires PERSON_TO_PERSON purpose")
        if self.context_type is ContextType.P2P and not self.continuity_uid:
            raise ValueError("continuity_uid is required for P2P context")

        payload: dict[str, Any] = {
            "origin_system": require_text("origin_system", self.origin_system).upper(),
            "origin_intent_id": require_text(
                "origin_intent_id", self.origin_intent_id
            ),
            "context_type": self.context_type.value,
            "purpose": self.purpose.value,
        }
        for name, value in (
            ("continuity_uid", self.continuity_uid),
            ("merchant_id", self.merchant_id),
            ("branch_id", self.branch_id),
            ("partner_id", self.partner_id),
        ):
            if value is not None:
                payload[name] = require_text(name, value)
        return payload


@dataclass(frozen=True, slots=True)
class QuoteTerms:
    request_id: str
    payer: ActorReference
    beneficiary: ActorReference
    purpose: PaymentPurpose
    amount_minor: int
    currency_from: str
    receive_amount_minor: int
    currency_to: str
    total_fee_minor: int
    routing_budget_minor: int
    fx_rate: str
    corridor_id: str
    service_level: str
    routing_policy_id: str
    pricing_version: str
    max_attempts: int = 5

    def to_payload(self) -> dict[str, Any]:
        amount_minor = require_minor_units("amount_minor", self.amount_minor)
        receive_amount_minor = require_minor_units(
            "receive_amount_minor", self.receive_amount_minor
        )
        total_fee_minor = require_minor_units(
            "total_fee_minor", self.total_fee_minor, allow_zero=True
        )
        routing_budget_minor = require_minor_units(
            "routing_budget_minor", self.routing_budget_minor, allow_zero=True
        )
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if routing_budget_minor > total_fee_minor:
            raise ValueError("routing budget cannot exceed the customer fee")

        fx_rate = require_text("fx_rate", self.fx_rate)
        try:
            if Decimal(fx_rate) <= 0:
                raise ValueError("fx_rate must be positive")
        except InvalidOperation as exc:
            raise ValueError("fx_rate must be a decimal string") from exc

        if self.payer.endpoint.role is not AccountRole.DEBIT:
            raise ValueError("payer endpoint must be a DEBIT binding")
        if self.beneficiary.endpoint.role is not AccountRole.CREDIT:
            raise ValueError("beneficiary endpoint must be a CREDIT binding")
        return {
            "request_id": require_text("request_id", self.request_id),
            "payer": self.payer.to_payload(),
            "beneficiary": self.beneficiary.to_payload(),
            "purpose": self.purpose.value,
            "amount_minor": amount_minor,
            "currency_from": require_text(
                "currency_from", self.currency_from
            ).upper(),
            "receive_amount_minor": receive_amount_minor,
            "currency_to": require_text("currency_to", self.currency_to).upper(),
            "total_fee_minor": total_fee_minor,
            "routing_budget_minor": routing_budget_minor,
            "fx_rate": fx_rate,
            "corridor_id": require_text("corridor_id", self.corridor_id),
            "service_level": require_text("service_level", self.service_level),
            "routing_policy_id": require_text(
                "routing_policy_id", self.routing_policy_id
            ),
            "pricing_version": require_text(
                "pricing_version", self.pricing_version
            ),
            "pricing_model": "PER_INTENT",
            "max_attempts": self.max_attempts,
            "custody_model": "NON_CUSTODIAL",
            "endpoint_model_version": 1,
        }
