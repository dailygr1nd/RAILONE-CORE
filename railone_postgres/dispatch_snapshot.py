"""Build institutional dispatch expectations from verified RailOne records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from railone_contracts.models import AccountEndpoint, AccountRole, ContextType
from railone_authority.bilateral import BilateralAuthorityService
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService
from railone_execution.models import AttemptState, PlanStatus, require_aware
from railone_identity.models import IdentityStatus
from railone_institutions.wrapper import AuthoritativeDispatchSnapshot
from railone_operations.service import provider_idempotency_key

from .codec import envelope_from_db
from .contracts import PostgresContractStore
from .execution import PostgresExecutionStore
from .identity import PostgresIdentityRepository
from .institutions import PostgresInstitutionManifestStore
from .partners import PostgresPartnerDirectory
from .runtime import PostgresDatabase


class PostgresDispatchSnapshotReader:
    """Read-only P2P sandbox boundary. Raw account endpoints stay in the vault."""

    def __init__(
        self, database: PostgresDatabase, *, signatures: SignatureService,
        core_owner_id: str, require_sender_first: bool = False,
    ) -> None:
        self._database = database
        self._signatures = signatures
        self._core_owner_id = core_owner_id
        self._require_sender_first = require_sender_first
        self._contracts = PostgresContractStore(database)
        self._executions = PostgresExecutionStore(database)
        self._identities = PostgresIdentityRepository(database)
        self._manifests = PostgresInstitutionManifestStore(database)
        self._partners = PostgresPartnerDirectory(database)

    def load(self, *, rtt_id: str, at: datetime) -> AuthoritativeDispatchSnapshot:
        instant = require_aware("dispatch snapshot timestamp", at)
        attempt = self._executions.require_attempt(rtt_id)
        plan = self._executions.require_plan(attempt.plan_id)
        if (attempt.state is not AttemptState.CREATED or plan.status is not PlanStatus.ACTIVE
                or plan.utt_id != attempt.utt_id or plan.current_rtt_id != rtt_id
                or plan.attempts_used != attempt.attempt_number):
            raise PermissionError("RTT is not the current active attempt")
        utt_envelope = self._contracts.require_utt(attempt.utt_id)
        utt = self._verified(utt_envelope, ArtifactType.UTT, instant)
        rtt = self._verified(attempt.signed_rtt, ArtifactType.RTT, instant)
        utt_digest = utt_envelope.protected["payload_sha256"]
        if (
            utt["utt_id"], rtt["utt_id"], rtt["plan_id"], rtt["rtt_id"],
            rtt["attempt_number"], rtt["replay_generation"], rtt["utt_payload_sha256"],
        ) != (
            attempt.utt_id, attempt.utt_id, plan.plan_id, rtt_id,
            attempt.attempt_number, attempt.attempt_number - 1, utt_digest,
        ):
            raise PermissionError("signed UTT and RTT lineage does not match the active plan")
        decision = self._executions.require_decision_for_plan(plan.plan_id)
        decision.verify(plan=plan, expected_utt_payload_sha256=utt_digest)
        decision_body = decision.payload
        request = decision_body["request"]
        if (decision_body["routing_policy_id"], request["amount_minor"],
                request["currency_from"], request["currency_to"],
                request["routing_budget_minor"], request["source_institution_id"],
                request["destination_institution_id"]) != (
                utt["routing_policy_id"], utt["amount_minor"],
                utt["currency_from"], utt["currency_to"], utt["routing_budget_minor"],
                utt["payer"]["endpoint"]["institution_id"],
                utt["beneficiary"]["endpoint"]["institution_id"]):
            raise PermissionError("route decision inputs do not match the accepted UTT")
        route = rtt["route"]
        if route["route_id"] != attempt.route_id or not any(
            ranked.candidate.to_payload() == route
            and ranked.score_bps == rtt["route_score_bps"]
            and dict(ranked.component_scores) == rtt["route_component_scores"]
            for ranked in plan.ranked_routes
        ):
            raise PermissionError("signed RTT route does not match the verified plan ranking")

        payer, recipient = utt["payer"], utt["beneficiary"]
        sender_uid, recipient_uid = payer["actor_id"], recipient["actor_id"]
        origin = utt["origin"]
        if origin["context_type"] != ContextType.P2P.value or origin.get("continuity_uid") != sender_uid:
            raise PermissionError("sandbox snapshot requires a continuity-bound P2P UTT")
        for uid in (sender_uid, recipient_uid):
            identity = self._identities.get_by_continuity_uid(uid)
            if (identity is None or identity.identity.status is not IdentityStatus.ACTIVE
                    or identity.active_revision.status is not IdentityStatus.ACTIVE):
                raise PermissionError("dispatch requires active sender and recipient identities")
        debit = AccountEndpoint.from_payload(payer["endpoint"])
        credit = AccountEndpoint.from_payload(recipient["endpoint"])
        self._partners.validate_endpoint(
            actor_id=sender_uid, endpoint=debit, required_role=AccountRole.DEBIT,
            currency=utt["currency_from"],
        )
        self._partners.validate_endpoint(
            actor_id=recipient_uid, endpoint=credit, required_role=AccountRole.CREDIT,
            currency=utt["currency_to"],
        )
        if (route["source_institution_id"], route["destination_institution_id"],
                route["currency_from"], route["currency_to"]) != (
                debit.institution_id, credit.institution_id, utt["currency_from"], utt["currency_to"]):
            raise PermissionError("signed RTT route does not match the accepted endpoints")

        sender, receiver, fence = self._read_authority_and_fence(attempt.utt_id, utt["etk_s_id"])
        if utt.get("authority_version") == 2:
            # Superseded v2 signed in the opposite order; fail closed.
            raise PermissionError("RECEIVER_FIRST_V2_DEPRECATED")
        if utt.get("authority_version") == 4:
            BilateralAuthorityService(self._signatures).verify_utt(
                signed_utt=utt_envelope, sender=sender, receiver=receiver, at=instant,
            )
            if (utt.get("etk_r_id") != receiver.payload.get("etk_r_id")
                    or utt.get("etk_s_id") != sender.payload.get("etk_s_id")):
                raise PermissionError("persisted bilateral authorities do not match UTT")
        else:
            if self._require_sender_first or utt.get("authority_version") not in (None, 1):
                raise PermissionError("SENDER_FIRST_BILATERAL_V4_REQUIRED")
            # Legacy ETK-S-first verification, retained only for existing fixtures.
            etk_s = self._verified(sender, ArtifactType.ETK_S, instant)
            etk_r = self._verified(receiver, ArtifactType.ETK_R, instant)
            epoch = int(instant.timestamp())
            if (etk_s["utt_id"], etk_s["etk_s_id"], etk_s["quote_id"],
                    etk_s["sender_actor_type"], etk_s["sender_reference"],
                    etk_s["amount_minor"], etk_s["currency"], etk_s["origin_context"],
                    etk_s["authority_scope"], etk_s["status"]) != (
                    attempt.utt_id, utt["etk_s_id"], utt["quote_id"], payer["actor_type"],
                    sender_uid, utt["amount_minor"], utt["currency_from"], origin,
                    "EXECUTE_UTT", "ACTIVE"):
                raise PermissionError("sender authority does not match the accepted UTT")
            if (etk_r["utt_id"], etk_r["etk_s_id"], etk_r["receiver_actor_type"],
                    etk_r["receiver_reference"], etk_r["amount_minor"], etk_r["currency"],
                    etk_r["status"]) != (
                    attempt.utt_id, utt["etk_s_id"], recipient["actor_type"], recipient_uid,
                    utt["amount_minor"], utt["currency_from"], "ACTIVE"):
                raise PermissionError("receiver authority does not match the accepted UTT")
            if not (etk_s["authorized_at"] <= etk_r["attested_at"] <= epoch
                    < etk_r["expires_at"] <= etk_s["expires_at"]):
                raise PermissionError("bilateral authority is outside its dispatch window")

        manifest = self._manifests.require(route["adapter"])
        provider_id = route["provider"].upper()
        if manifest.provider_id != provider_id:
            raise PermissionError("persisted manifest provider does not match the signed route")
        return AuthoritativeDispatchSnapshot(
            utt_id=attempt.utt_id, plan_id=plan.plan_id, rtt_id=rtt_id,
            attempt_number=attempt.attempt_number, replay_generation=rtt["replay_generation"],
            correlation_id=rtt_id, utt_payload_digest=utt_digest,
            rtt_birth_digest=attempt.signed_rtt.protected["payload_sha256"],
            etk_s_digest=sender.protected["payload_sha256"],
            etk_r_digest=receiver.protected["payload_sha256"],
            sender_cont_uid=sender_uid, recipient_cont_uid=recipient_uid,
            adapter_binding_ref=route["adapter"], adapter_manifest_digest=manifest.payload_sha256,
            route_decision_digest=decision.decision_sha256, route_id=attempt.route_id,
            provider_id=provider_id, request_sha256=None,
            idempotency_key=provider_idempotency_key(provider_id=provider_id, rtt_id=rtt_id),
            source_amount_minor=utt["amount_minor"], source_currency=utt["currency_from"],
            receive_amount_minor=utt["receive_amount_minor"], receive_currency=utt["currency_to"],
            payer_binding_ref=debit.account_binding_id, beneficiary_binding_ref=credit.account_binding_id,
            source_routing_node=debit.institution_id, destination_routing_node=credit.institution_id,
            economic_effect_fence_epoch=1 if fence is None else fence["fence_epoch"],
            release_evidence_ref=None if fence is None else fence["last_release_evidence_id"],
        )

    def _verified(
        self, envelope: SignatureEnvelope, artifact: ArtifactType, at: datetime,
    ) -> Mapping[str, Any]:
        result = self._signatures.verify_artifact(envelope, expected_artifact_type=artifact)
        if (not result.valid or envelope.protected["iss"] != self._core_owner_id
                or envelope.protected["iat"] > int(at.timestamp())):
            raise PermissionError(f"invalid trusted {artifact.value} artifact")
        return envelope.payload

    def _read_authority_and_fence(
        self, utt_id: str, sender_id: str,
    ) -> tuple[SignatureEnvelope, SignatureEnvelope, Mapping[str, Any] | None]:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT authority_id, authority_type, signed_envelope
                   FROM railone.execution_authorities
                   WHERE utt_id=%s AND ((authority_type='ETK_S' AND authority_id=%s)
                                        OR authority_type='ETK_R')
                   ORDER BY authority_type, authority_id LIMIT 3""",
                (utt_id, sender_id),
            )
            rows = cursor.fetchall()
            if [row["authority_type"] for row in rows] != ["ETK_R", "ETK_S"]:
                raise PermissionError("dispatch requires one persisted receiver and sender authority")
            receiver, sender = [envelope_from_db(row["signed_envelope"]) for row in rows]
            if receiver.payload.get("etk_r_id") != rows[0]["authority_id"]:
                raise PermissionError("receiver authority identifier does not match its record")
            cursor.execute(
                """SELECT fence_epoch, last_release_evidence_id
                   FROM railone.utt_economic_fences WHERE utt_id=%s""", (utt_id,),
            )
            return sender, receiver, cursor.fetchone()
