"""Passive, versioned sovereign-currency and settlement-instrument definitions.

These metadata records do NOT authorize routing, custody, dispatch, settlement,
CBDC access, or regulated activity. An authorization layer must separately
verify authoritative evidence and institutional permissions before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{1,127}$")


def _code(name: str, value: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{name} must be in its canonical identifier format")
    return value


def _reference(name: str, value: str) -> str:
    return _code(name, value, _REFERENCE)


def _positive_version(name: str, value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


class SettlementInstrumentKind(StrEnum):
    COMMERCIAL_BANK_MONEY = "COMMERCIAL_BANK_MONEY"
    REGULATED_E_MONEY = "REGULATED_E_MONEY"
    RETAIL_CBDC = "RETAIL_CBDC"
    WHOLESALE_CBDC = "WHOLESALE_CBDC"


class MonetaryIssuerKind(StrEnum):
    CENTRAL_BANK = "CENTRAL_BANK"
    LICENSED_BANK = "LICENSED_BANK"
    REGULATED_EMONEY_ISSUER = "REGULATED_EMONEY_ISSUER"


class InstrumentEnvironment(StrEnum):
    SANDBOX = "SANDBOX"
    PILOT = "PILOT"
    PRODUCTION = "PRODUCTION"


class ProfileReviewStatus(StrEnum):
    DECLARED = "DECLARED"
    REVIEWED = "REVIEWED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True, slots=True)
class CurrencyDefinition:
    """A sovereign-denomination reference; not a live-execution permission."""

    currency_code: str
    definition_version: int
    minor_unit_exponent: int
    issuing_authority_ref: str
    standard_reference: str

    def __post_init__(self) -> None:
        _code("currency_code", self.currency_code, _CURRENCY_CODE)
        _positive_version("definition_version", self.definition_version)
        if type(self.minor_unit_exponent) is not int or not 0 <= self.minor_unit_exponent <= 9:
            raise ValueError("minor_unit_exponent must be an integer from 0 through 9")
        _reference("issuing_authority_ref", self.issuing_authority_ref)
        _reference("standard_reference", self.standard_reference)

    def to_payload(self) -> dict[str, str | int]:
        return {
            "currency_code": self.currency_code,
            "definition_version": self.definition_version,
            "minor_unit_exponent": self.minor_unit_exponent,
            "issuing_authority_ref": self.issuing_authority_ref,
            "standard_reference": self.standard_reference,
        }


@dataclass(frozen=True, slots=True)
class SettlementInstrumentProfile:
    """A declared rail/instrument capability; never a dispatch authorization."""

    profile_id: str
    profile_version: int
    currency_code: str
    currency_definition_version: int
    instrument_kind: SettlementInstrumentKind
    issuer_kind: MonetaryIssuerKind
    issuer_institution_id: str
    operator_institution_id: str
    settlement_rail_id: str
    jurisdiction_country: str
    environment: InstrumentEnvironment
    review_status: ProfileReviewStatus = ProfileReviewStatus.DECLARED
    review_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _reference("profile_id", self.profile_id)
        _positive_version("profile_version", self.profile_version)
        _code("currency_code", self.currency_code, _CURRENCY_CODE)
        _positive_version("currency_definition_version", self.currency_definition_version)
        for name in ("issuer_institution_id", "operator_institution_id", "settlement_rail_id"):
            _reference(name, getattr(self, name))
        _code("jurisdiction_country", self.jurisdiction_country, _COUNTRY_CODE)
        for name, enum_type in (
            ("instrument_kind", SettlementInstrumentKind),
            ("issuer_kind", MonetaryIssuerKind),
            ("environment", InstrumentEnvironment),
            ("review_status", ProfileReviewStatus),
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise ValueError(f"{name} must be a supported {enum_type.__name__}")

        expected_issuer = {
            SettlementInstrumentKind.COMMERCIAL_BANK_MONEY: MonetaryIssuerKind.LICENSED_BANK,
            SettlementInstrumentKind.REGULATED_E_MONEY: MonetaryIssuerKind.REGULATED_EMONEY_ISSUER,
            SettlementInstrumentKind.RETAIL_CBDC: MonetaryIssuerKind.CENTRAL_BANK,
            SettlementInstrumentKind.WHOLESALE_CBDC: MonetaryIssuerKind.CENTRAL_BANK,
        }[self.instrument_kind]
        if self.issuer_kind is not expected_issuer:
            raise ValueError("instrument kind and issuer kind are inconsistent")
        if self.review_evidence_ref is not None:
            _reference("review_evidence_ref", self.review_evidence_ref)
        if self.review_status is ProfileReviewStatus.REVIEWED and self.review_evidence_ref is None:
            raise ValueError("reviewed profiles must reference review evidence")

    def to_payload(self) -> dict[str, str | int | None]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "currency_code": self.currency_code,
            "currency_definition_version": self.currency_definition_version,
            "instrument_kind": self.instrument_kind.value,
            "issuer_kind": self.issuer_kind.value,
            "issuer_institution_id": self.issuer_institution_id,
            "operator_institution_id": self.operator_institution_id,
            "settlement_rail_id": self.settlement_rail_id,
            "jurisdiction_country": self.jurisdiction_country,
            "environment": self.environment.value,
            "review_status": self.review_status.value,
            "review_evidence_ref": self.review_evidence_ref,
        }
