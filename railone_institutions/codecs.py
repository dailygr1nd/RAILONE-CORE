"""Canonical JSON and ISO 20022 message-codec boundaries."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Protocol
from xml.etree import ElementTree as ET

from railone_crypto.canonical_json import canonical_json_bytes

from .models import InstitutionExecutionInstruction


class InstitutionMessageCodec(Protocol):
    content_type: str

    def encode_submission(self, instruction: InstitutionExecutionInstruction) -> bytes: ...


def _wire_payload(instruction: InstitutionExecutionInstruction) -> dict[str, object]:
    return {
        "idempotency_key": instruction.idempotency_key,
        "request_sha256": instruction.request_sha256,
        "utt_id": instruction.utt_id,
        "rtt_id": instruction.rtt_id,
        "attempt_number": instruction.attempt_number,
        "provider_id": instruction.provider_id,
        "adapter_binding_ref": instruction.adapter_binding_ref,
        "rail": instruction.rail,
        "amount_minor": instruction.amount_minor,
        "currency_from": instruction.currency_from,
        "receive_amount_minor": instruction.receive_amount_minor,
        "currency_to": instruction.currency_to,
        "source_institution_id": instruction.source_institution_id,
        "destination_institution_id": instruction.destination_institution_id,
        "payer_account_reference": instruction.payer_account_reference,
        "beneficiary_account_reference": instruction.beneficiary_account_reference,
    }


class CanonicalJsonCodec:
    content_type = "application/json"

    def encode_submission(self, instruction: InstitutionExecutionInstruction) -> bytes:
        return canonical_json_bytes(_wire_payload(instruction))


class Iso20022Pain001Codec:
    """Deterministic pain.001.001.09 pilot profile, not scheme certification."""

    content_type = "application/xml"
    namespace = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"

    def encode_submission(self, instruction: InstitutionExecutionInstruction) -> bytes:
        ET.register_namespace("", self.namespace)
        q = lambda name: f"{{{self.namespace}}}{name}"
        document = ET.Element(q("Document"))
        initiation = ET.SubElement(document, q("CstmrCdtTrfInitn"))
        header = ET.SubElement(initiation, q("GrpHdr"))
        ET.SubElement(header, q("MsgId")).text = instruction.rtt_id
        ET.SubElement(header, q("NbOfTxs")).text = "1"
        payment = ET.SubElement(initiation, q("PmtInf"))
        ET.SubElement(payment, q("PmtInfId")).text = instruction.idempotency_key
        transfer = ET.SubElement(payment, q("CdtTrfTxInf"))
        payment_id = ET.SubElement(transfer, q("PmtId"))
        ET.SubElement(payment_id, q("EndToEndId")).text = instruction.utt_id
        amount = ET.SubElement(transfer, q("Amt"))
        instructed = ET.SubElement(amount, q("InstdAmt"), Ccy=instruction.currency_from)
        instructed.text = str((Decimal(instruction.amount_minor) / Decimal(100)).quantize(Decimal("0.00")))
        debtor = ET.SubElement(transfer, q("DbtrAcct"))
        debtor_other = ET.SubElement(ET.SubElement(debtor, q("Id")), q("Othr"))
        ET.SubElement(debtor_other, q("Id")).text = instruction.payer_account_reference
        creditor = ET.SubElement(transfer, q("CdtrAcct"))
        creditor_other = ET.SubElement(ET.SubElement(creditor, q("Id")), q("Othr"))
        ET.SubElement(creditor_other, q("Id")).text = instruction.beneficiary_account_reference
        remittance = ET.SubElement(transfer, q("RmtInf"))
        ET.SubElement(remittance, q("Ustrd")).text = instruction.rtt_id
        return ET.tostring(document, encoding="utf-8", xml_declaration=True)


def decode_json_object(body: bytes, *, max_bytes: int = 1_000_000) -> dict[str, object]:
    if len(body) > max_bytes:
        raise ValueError("provider response exceeds codec limit")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("provider response must be a JSON object")
    return value
