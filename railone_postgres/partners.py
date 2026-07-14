"""PostgreSQL partner-institution and opaque account-binding directory."""

from __future__ import annotations

from datetime import datetime, timezone

from railone_contracts import AccountEndpoint, AccountRole, AccountType
from railone_partners import (
    AccountBinding, AccountBindingStatus, InstitutionStatus, PartnerInstitution,
)

from .runtime import PostgresDatabase


class PostgresPartnerDirectory:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def add_institution(
        self, institution: PartnerInstitution, *, at: datetime | None = None
    ) -> None:
        institution.normalized()
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.partner_institutions
                   (institution_id, display_name, country_codes, currencies,
                    supported_roles, status, version, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)""",
                (
                    institution.institution_id, institution.display_name,
                    list(institution.country_codes), list(institution.currencies),
                    [role.value for role in institution.supported_roles],
                    institution.status.value, instant, instant,
                ),
            )

    def add_binding(
        self, binding: AccountBinding, *, at: datetime | None = None
    ) -> None:
        binding.normalized()
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.account_bindings
                   (account_binding_id, actor_id, institution_id, role,
                    account_type, currency, display_hint, contact_binding_id,
                    attestation_reference, status, version, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)""",
                (
                    binding.account_binding_id, binding.actor_id,
                    binding.institution_id, binding.role.value,
                    binding.account_type.value, binding.currency.upper(),
                    binding.display_hint, binding.contact_binding_id,
                    binding.attestation_reference, binding.status.value,
                    instant, instant,
                ),
            )

    def list_institutions(self, *, country_code, currency, role):
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT institution_id, display_name, country_codes,
                          currencies, supported_roles, status
                   FROM railone.partner_institutions
                   WHERE status='ACTIVE' AND %s=ANY(country_codes)
                     AND %s=ANY(currencies) AND %s=ANY(supported_roles)
                   ORDER BY institution_id""",
                (country_code.upper(), currency.upper(), role.value),
            )
            return tuple(_institution(row) for row in cursor.fetchall())

    def select_endpoint(self, *, actor_id, account_binding_id, required_role):
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT b.account_binding_id, b.actor_id, b.institution_id,
                          b.role, b.account_type, b.currency, b.display_hint,
                          b.contact_binding_id, b.attestation_reference, b.status,
                          i.display_name, i.status AS institution_status
                   FROM railone.account_bindings b
                   JOIN railone.partner_institutions i
                     ON i.institution_id=b.institution_id
                   WHERE b.account_binding_id=%s""",
                (account_binding_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("account binding not found")
            if row["actor_id"] != actor_id:
                raise PermissionError("account binding belongs to another actor")
            if row["status"] != "ACTIVE" or row["institution_status"] != "ACTIVE":
                raise PermissionError("account binding or institution is not active")
            if row["role"] != required_role.value:
                raise PermissionError("account binding has the wrong execution role")
            return AccountEndpoint(
                institution_id=str(row["institution_id"]),
                institution_display_name=str(row["display_name"]),
                account_binding_id=str(row["account_binding_id"]),
                role=AccountRole(row["role"]),
                account_type=AccountType(row["account_type"]),
                display_hint=str(row["display_hint"]),
                contact_binding_id=str(row["contact_binding_id"]),
                attestation_reference=str(row["attestation_reference"]),
            )

    def validate_endpoint(
        self, *, actor_id, endpoint, required_role, currency
    ) -> None:
        selected = self.select_endpoint(
            actor_id=actor_id, account_binding_id=endpoint.account_binding_id,
            required_role=required_role,
        )
        if not (
            selected.institution_id == endpoint.institution_id
            and selected.account_binding_id == endpoint.account_binding_id
            and selected.role is endpoint.role
            and selected.account_type is endpoint.account_type
            and selected.display_hint == endpoint.display_hint
            and selected.contact_binding_id == endpoint.contact_binding_id
            and selected.attestation_reference == endpoint.attestation_reference
        ):
            raise PermissionError("account endpoint snapshot does not match its binding")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT currency FROM railone.account_bindings WHERE account_binding_id=%s",
                (endpoint.account_binding_id,),
            )
            row = cursor.fetchone()
            if row is None or str(row["currency"]).upper() != currency.upper():
                raise PermissionError("account binding currency is not eligible")


def _institution(row):
    return PartnerInstitution(
        institution_id=str(row["institution_id"]),
        display_name=str(row["display_name"]),
        country_codes=tuple(row["country_codes"]),
        currencies=tuple(row["currencies"]),
        supported_roles=tuple(AccountRole(value) for value in row["supported_roles"]),
        status=InstitutionStatus(row["status"]),
    )
