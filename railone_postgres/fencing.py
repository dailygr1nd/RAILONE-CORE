"""Durable, conservative UTT economic-effect fencing with per-RTT lineage.

A reservation is a financial-effect *possibility*, not a lease. A process crash,
provider timeout, or an accepted-for-processing response NEVER releases it.
Release requires an independently signed NO_ECONOMIC_EFFECT attestation from a
specifically trusted settlement/reconciliation signing key. The signer must
verify the original provider evidence before issuing an attestation.

This repository is for INSTITUTIONAL_SANDBOX only. It does not grant live access.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService
from .codec import json_text
from .runtime import PostgresDatabase

_HEX = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9._:-]{3,128}$")
_ALLOWED_OUTCOMES = {
    "ACCEPTED": ("ACCEPTED_FOR_PROCESSING", "PROVIDER_ACCEPTED"),
    "REJECTED": ("REJECTED", "PROVIDER_REJECTED"),
    "UNKNOWN": ("UNKNOWN", "PROVIDER_UNKNOWN"),
}


class EconomicFenceViolation(PermissionError):
    """Dispatch or release lacks durable proof of economic safety."""


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("fence timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _epoch(value: int) -> int:
    if type(value) is not int or not 1 <= value < 2**63:
        raise ValueError("economic fence epoch must be a positive integer")
    return value


class PostgresEconomicEffectFence:
    """Enforces a UTT-wide hold and RTT-specific operational state using row locks.

    reserve_dispatch() is the only authorization-changing operation. The UTT row
    is locked before checking the attempt, plan, and current fence. No expired
    lease, HTTP retry, or process restart can implicitly release a reservation.
    """

    def __init__(
        self, database: PostgresDatabase, *, signatures: SignatureService,
        trusted_no_effect_signing_keys: frozenset[str],
    ) -> None:
        if not trusted_no_effect_signing_keys:
            raise ValueError("at least one trusted no-effect signer is required")
        self._database = database
        self._signatures = signatures
        self._trusted_keys = frozenset(trusted_no_effect_signing_keys)

    @staticmethod
    def _assert_epoch(row, *, epoch: int, release_ref: str | None) -> None:
        if row is None:
            if epoch != 1 or release_ref is not None:
                raise EconomicFenceViolation("first dispatch requires epoch 1 and no release")
        elif (row["state"] != "OPEN" or row["fence_epoch"] != epoch
              or row["last_release_evidence_id"] != release_ref):
            raise EconomicFenceViolation("economic effect is held, final, or at a different epoch")

    def assert_dispatch_safe(
        self, *, utt_id: str, rtt_id: str, fence_epoch: int,
        release_evidence_ref: str | None, at: datetime,
    ) -> None:
        _time(at)
        _epoch(fence_epoch)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT fence_epoch,state,last_release_evidence_id "
                "FROM railone.utt_economic_fences WHERE utt_id=%s", (utt_id,)
            )
            row = cursor.fetchone()
            self._assert_epoch(row, epoch=fence_epoch, release_ref=release_evidence_ref)
            cursor.execute(
                "SELECT 1 FROM railone.settlement_evidence WHERE utt_id=%s", (utt_id,)
            )
            if cursor.fetchone() is not None:
                raise EconomicFenceViolation("existing settlement prohibits admission")
            cursor.execute(
                """SELECT a.rtt_id FROM railone.rtt_attempts AS a
                   JOIN railone.execution_plans AS p ON p.plan_id=a.plan_id
                   WHERE a.rtt_id=%s AND a.utt_id=%s AND a.state='CREATED'
                   AND p.utt_id=%s AND p.current_rtt_id=a.rtt_id
                   AND p.status='ACTIVE'""",
                (rtt_id, utt_id, utt_id),
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("RTT is not the current eligible attempt")

    def reserve_dispatch(
        self, *, utt_id: str, rtt_id: str, fence_epoch: int,
        release_evidence_ref: str | None, request_sha256: str, at: datetime,
    ) -> None:
        """Atomically reserve the UTT economic effect for exactly this RTT.

        The reservation commits BEFORE a network call. Crash after commit is
        deliberately fail-closed, requiring reconciliation before another RTT.
        """
        instant = _time(at)
        _epoch(fence_epoch)
        if not isinstance(request_sha256, str) or not _HEX.fullmatch(request_sha256):
            raise ValueError("invalid prepared provider-request digest")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            # Every contender locks the same already-existing accepted UTT row,
            # including when the fence row has not yet been initialized.
            cursor.execute(
                "SELECT utt_id FROM railone.accepted_utts WHERE utt_id=%s FOR UPDATE", (utt_id,)
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("accepted UTT not found")
            cursor.execute(
                "SELECT 1 FROM railone.settlement_evidence WHERE utt_id=%s", (utt_id,)
            )
            if cursor.fetchone() is not None:
                raise EconomicFenceViolation("existing settlement prohibits any new dispatch")
            cursor.execute(
                """SELECT a.rtt_id FROM railone.rtt_attempts AS a
                   JOIN railone.execution_plans AS p ON p.plan_id=a.plan_id
                   JOIN railone.provider_submissions AS s ON s.rtt_id=a.rtt_id
                   WHERE a.rtt_id=%s AND a.utt_id=%s AND a.state='CREATED'
                   AND p.utt_id=%s AND p.current_rtt_id=a.rtt_id
                   AND p.status='ACTIVE' AND s.state='PREPARED'
                   AND s.request_sha256=%s""",
                (rtt_id, utt_id, utt_id, request_sha256),
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("RTT, plan or prepared request changed before reservation")
            cursor.execute(
                """SELECT fence_epoch,state,last_release_evidence_id
                   FROM railone.utt_economic_fences WHERE utt_id=%s FOR UPDATE""", (utt_id,)
            )
            existing = cursor.fetchone()
            self._assert_epoch(existing, epoch=fence_epoch, release_ref=release_evidence_ref)
            if existing is None:
                cursor.execute(
                    """INSERT INTO railone.utt_economic_fences
                       (utt_id,fence_epoch,state,current_rtt_id,last_release_evidence_id,
                        created_at,updated_at) VALUES (%s,%s,'HELD',%s,NULL,%s,%s)""",
                    (utt_id, fence_epoch, rtt_id, instant, instant),
                )
            else:
                cursor.execute(
                    """UPDATE railone.utt_economic_fences
                       SET state='HELD',current_rtt_id=%s,version=version+1,updated_at=%s
                       WHERE utt_id=%s AND state='OPEN' AND fence_epoch=%s""",
                    (rtt_id, instant, utt_id, fence_epoch),
                )
                if cursor.rowcount != 1:
                    raise EconomicFenceViolation("economic fence changed concurrently")
            cursor.execute(
                """INSERT INTO railone.rtt_operational_fences
                   (rtt_id,utt_id,fence_epoch,request_sha256,state,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,'RESERVED',%s,%s)""",
                (rtt_id, utt_id, fence_epoch, request_sha256, instant, instant),
            )
            self._event(cursor, utt_id, rtt_id, fence_epoch, "RESERVED", None, instant)

    def record_provider_outcome(
        self, *, utt_id: str, rtt_id: str, outcome: str, at: datetime,
    ) -> None:
        """Record provider observation; NEVER clear the UTT economic hold."""
        instant = _time(at)
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported provider outcome")
        state, event = _ALLOWED_OUTCOMES[outcome]
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT fence_epoch FROM railone.utt_economic_fences
                   WHERE utt_id=%s AND current_rtt_id=%s AND state='HELD' FOR UPDATE""",
                (utt_id, rtt_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise EconomicFenceViolation("provider outcome cannot change a released fence")
            cursor.execute(
                """UPDATE railone.rtt_operational_fences SET state=%s,updated_at=%s
                   WHERE rtt_id=%s AND utt_id=%s AND state IN
                   ('RESERVED','UNKNOWN','ACCEPTED_FOR_PROCESSING','REJECTED')""",
                (state, instant, rtt_id, utt_id),
            )
            if cursor.rowcount != 1:
                raise EconomicFenceViolation("RTT operational fence cannot change state")
            self._event(cursor, utt_id, rtt_id, row["fence_epoch"], event, None, instant)

    def release_verified_no_effect(
        self, *, evidence: SignatureEnvelope, at: datetime,
    ) -> int:
        """Advance epoch only after signed evidence is validated and stored.

        Trust of the signer is necessary but not sufficient: the *external*
        reconciliation service must independently verify the bank/provider proof
        before issuing this purpose-separated attestation.
        """
        instant = _time(at)
        result = self._signatures.verify_artifact(
            evidence, expected_artifact_type=ArtifactType.NO_EFFECT_EVIDENCE
        )
        if not result.valid or result.key_id not in self._trusted_keys:
            raise EconomicFenceViolation("no-effect evidence signature or signer is not trusted")
        p = evidence.payload
        if set(p) != {"evidence_id","utt_id","rtt_id","provider_id","finding",
                      "source_evidence_digest","observed_at_epoch"}:
            raise EconomicFenceViolation("no-effect attestation has unexpected fields")
        if p["finding"] != "NO_ECONOMIC_EFFECT":
            raise EconomicFenceViolation("attestation is not proof of no effect")
        if any(not isinstance(p[k], str) or not _OPAQUE.fullmatch(p[k])
               for k in ("evidence_id","utt_id","rtt_id","provider_id")):
            raise EconomicFenceViolation("invalid no-effect evidence reference")
        if not isinstance(p["source_evidence_digest"], str) or not _HEX.fullmatch(p["source_evidence_digest"]):
            raise EconomicFenceViolation("no-effect source artifact must be digest-bound")
        if type(p["observed_at_epoch"]) is not int or not p["observed_at_epoch"] <= evidence.protected["iat"] <= int(instant.timestamp()):
            raise EconomicFenceViolation("no-effect evidence observation time is invalid")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            # Use the same UTT lock order as reservation and settlement insertion,
            # so releases cannot race a newly persisted settlement record.
            cursor.execute(
                "SELECT utt_id FROM railone.accepted_utts WHERE utt_id=%s FOR UPDATE",
                (p["utt_id"],),
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("attested UTT does not exist")
            cursor.execute(
                """SELECT fence_epoch,current_rtt_id FROM railone.utt_economic_fences
                   WHERE utt_id=%s AND state='HELD' FOR UPDATE""", (p["utt_id"],)
            )
            row = cursor.fetchone()
            if row is None or row["current_rtt_id"] != p["rtt_id"]:
                raise EconomicFenceViolation("attestation does not match active economic hold")
            if row["fence_epoch"] >= 2**63 - 1:
                raise EconomicFenceViolation("economic fence epoch exhausted")
            cursor.execute(
                """SELECT 1 FROM railone.provider_submissions s
                   JOIN railone.rtt_operational_fences f USING (utt_id,rtt_id)
                   WHERE s.rtt_id=%s AND s.utt_id=%s AND s.provider_id=%s
                     AND f.created_at <= to_timestamp(%s)""",
                (p["rtt_id"], p["utt_id"], p["provider_id"], p["observed_at_epoch"]),
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("attestation does not match submission and reservation time")
            cursor.execute(
                """SELECT 1 FROM railone.settlement_evidence
                   WHERE utt_id=%s""", (p["utt_id"],)
            )
            if cursor.fetchone() is not None:
                raise EconomicFenceViolation("existing settlement evidence prohibits release")
            cursor.execute(
                """INSERT INTO railone.economic_fence_no_effect_evidence
                   (evidence_id,utt_id,rtt_id,signed_evidence,evidence_sha256,
                    signing_key_id,recorded_at)
                   VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (p["evidence_id"], p["utt_id"], p["rtt_id"],
                 json_text(evidence.to_dict()), evidence.protected["payload_sha256"],
                 result.key_id, instant),
            )
            cursor.execute(
                """UPDATE railone.rtt_operational_fences
                   SET state='RELEASED_NO_EFFECT',updated_at=%s
                   WHERE rtt_id=%s AND state IN
                   ('RESERVED','UNKNOWN','REJECTED','ACCEPTED_FOR_PROCESSING')""",
                (instant, p["rtt_id"]),
            )
            if cursor.rowcount != 1:
                raise EconomicFenceViolation("RTT operational fence cannot be released")
            next_epoch = row["fence_epoch"] + 1
            cursor.execute(
                """UPDATE railone.utt_economic_fences
                   SET fence_epoch=%s,state='OPEN',current_rtt_id=NULL,
                       last_release_evidence_id=%s,version=version+1,updated_at=%s
                   WHERE utt_id=%s AND state='HELD'""",
                (next_epoch, p["evidence_id"], instant, p["utt_id"]),
            )
            self._event(cursor, p["utt_id"], p["rtt_id"], row["fence_epoch"],
                        "VERIFIED_NO_EFFECT", p["evidence_id"], instant)
            return next_epoch

    def mark_settled_from_verified_evidence(
        self, *, utt_id: str, rtt_id: str, evidence_id: str, at: datetime,
    ) -> None:
        """Finalize only a matching, independently persisted settlement proof."""
        instant = _time(at)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT utt_id FROM railone.accepted_utts WHERE utt_id=%s FOR UPDATE",
                (utt_id,),
            )
            if cursor.fetchone() is None:
                raise EconomicFenceViolation("settlement UTT is not recognized")
            self.finalize_locked(cursor, utt_id, rtt_id, evidence_id, instant)

    @staticmethod
    def finalize_locked(cursor, utt_id, rtt_id, evidence_id, instant):
        """Caller holds the accepted UTT row lock until transaction commit."""
        cursor.execute(
            """SELECT fence_epoch,state FROM railone.utt_economic_fences
               WHERE utt_id=%s AND current_rtt_id=%s FOR UPDATE""",
            (utt_id, rtt_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise EconomicFenceViolation("late or mismatched settlement needs operator escalation")
        if row["state"] == "FINALIZED":
            cursor.execute("SELECT 1 FROM railone.economic_fence_events WHERE utt_id=%s "
                           "AND rtt_id=%s AND event_type='SETTLED' AND evidence_id=%s",
                           (utt_id, rtt_id, evidence_id))
            if cursor.fetchone() is not None:
                return
        if row["state"] != "HELD":
            raise EconomicFenceViolation("settlement conflicts with current fence")
        cursor.execute(
            """SELECT 1 FROM railone.correlated_settlement_evidence
               WHERE evidence_id=%s AND utt_id=%s AND rtt_id=%s""",
            (evidence_id, utt_id, rtt_id),
        )
        if cursor.fetchone() is None:
            raise EconomicFenceViolation("settlement evidence is not correlated to reserved RTT")
        cursor.execute(
            """UPDATE railone.utt_economic_fences
               SET state='FINALIZED',version=version+1,updated_at=%s
               WHERE utt_id=%s AND state='HELD'""", (instant, utt_id),
        )
        cursor.execute(
            """UPDATE railone.rtt_operational_fences SET state='SETTLED',updated_at=%s
               WHERE rtt_id=%s AND state IN ('RESERVED','UNKNOWN','ACCEPTED_FOR_PROCESSING','REJECTED')""",
            (instant, rtt_id),
        )
        if cursor.rowcount != 1:
            raise EconomicFenceViolation("cannot finalize RTT operational fence")
        PostgresEconomicEffectFence._event(cursor, utt_id, rtt_id, row["fence_epoch"],
                    "SETTLED", evidence_id, instant)

    @staticmethod
    def _event(cursor, utt_id: str, rtt_id: str, epoch: int, kind: str,
               evidence_id: str | None, instant: datetime) -> None:
        cursor.execute(
            """INSERT INTO railone.economic_fence_events
               (utt_id,rtt_id,fence_epoch,event_type,evidence_id,recorded_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (utt_id, rtt_id, epoch, kind, evidence_id, instant),
        )
