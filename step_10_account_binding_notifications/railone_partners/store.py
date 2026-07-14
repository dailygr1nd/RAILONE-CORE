from __future__ import annotations

from threading import RLock
from dataclasses import replace
from typing import Protocol

from railone_contracts.models import AccountEndpoint, AccountRole

from .models import (
    AccountBinding,
    AccountBindingStatus,
    InstitutionStatus,
    PartnerInstitution,
)


class EndpointValidator(Protocol):
    def validate_endpoint(
        self,
        *,
        actor_id: str,
        endpoint: AccountEndpoint,
        required_role: AccountRole,
        currency: str,
    ) -> None: ...


class InMemoryPartnerDirectory:
    """Reference directory; production persists and audits these records."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._institutions: dict[str, PartnerInstitution] = {}
        self._bindings: dict[str, AccountBinding] = {}

    def add_institution(self, institution: PartnerInstitution) -> None:
        institution.normalized()
        with self._lock:
            if institution.institution_id in self._institutions:
                raise ValueError("partner institution already exists")
            self._institutions[institution.institution_id] = institution

    def add_binding(self, binding: AccountBinding) -> None:
        binding.normalized()
        with self._lock:
            institution = self._institutions.get(binding.institution_id)
            if institution is None:
                raise LookupError("account binding institution is not a partner")
            if binding.account_binding_id in self._bindings:
                raise ValueError("account binding already exists")
            self._bindings[binding.account_binding_id] = binding

    def set_binding_status(
        self, account_binding_id: str, status: AccountBindingStatus
    ) -> None:
        with self._lock:
            binding = self._bindings.get(account_binding_id)
            if binding is None:
                raise LookupError("account binding not found")
            self._bindings[account_binding_id] = replace(binding, status=status)

    def list_institutions(
        self, *, country_code: str, currency: str, role: AccountRole
    ) -> tuple[PartnerInstitution, ...]:
        with self._lock:
            rows = [
                item for item in self._institutions.values()
                if item.status is InstitutionStatus.ACTIVE
                and country_code.upper() in {value.upper() for value in item.country_codes}
                and currency.upper() in {value.upper() for value in item.currencies}
                and role in item.supported_roles
            ]
        return tuple(sorted(rows, key=lambda item: item.institution_id))

    def select_endpoint(
        self, *, actor_id: str, account_binding_id: str, required_role: AccountRole
    ) -> AccountEndpoint:
        with self._lock:
            binding = self._bindings.get(account_binding_id)
            if binding is None:
                raise LookupError("account binding not found")
            institution = self._institutions[binding.institution_id]
            if binding.actor_id != actor_id:
                raise PermissionError("account binding belongs to another actor")
            if binding.status is not AccountBindingStatus.ACTIVE:
                raise PermissionError("account binding is not active")
            if institution.status is not InstitutionStatus.ACTIVE:
                raise PermissionError("partner institution is not active")
            if binding.role is not required_role:
                raise PermissionError("account binding has the wrong execution role")
            return AccountEndpoint(
                institution_id=binding.institution_id,
                institution_display_name=institution.display_name,
                account_binding_id=binding.account_binding_id,
                role=binding.role,
                account_type=binding.account_type,
                display_hint=binding.display_hint,
                contact_binding_id=binding.contact_binding_id,
                attestation_reference=binding.attestation_reference,
            )

    def validate_endpoint(
        self,
        *,
        actor_id: str,
        endpoint: AccountEndpoint,
        required_role: AccountRole,
        currency: str,
    ) -> None:
        selected = self.select_endpoint(
            actor_id=actor_id,
            account_binding_id=endpoint.account_binding_id,
            required_role=required_role,
        )
        with self._lock:
            binding = self._bindings[endpoint.account_binding_id]
        if not _same_binding_material(selected, endpoint):
            raise PermissionError("account endpoint snapshot does not match its binding")
        if binding.currency.upper() != currency.upper():
            raise PermissionError("account binding currency is not eligible")


def _same_binding_material(left: AccountEndpoint, right: AccountEndpoint) -> bool:
    return (
        left.institution_id == right.institution_id
        and left.account_binding_id == right.account_binding_id
        and left.role is right.role
        and left.account_type is right.account_type
        and left.display_hint == right.display_hint
        and left.contact_binding_id == right.contact_binding_id
        and left.attestation_reference == right.attestation_reference
    )
