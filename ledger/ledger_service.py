# ==============================
# ledger_service.py (NON-CUSTODIAL)
# ==============================

from datetime import datetime
from uuid import uuid4

from ledger.models import JournalEntry


# --------------------------------
# INTERNAL: POST ENTRY
# --------------------------------
def _post(session, tx_id, account_id, amount, entry_type, currency):

    entry = JournalEntry(
        id=str(uuid4()),
        tx_id=tx_id,
        account_id=account_id,
        amount=float(amount),
        entry_type=entry_type,
        currency=currency,
        created_at=datetime.utcnow()
    )

    session.add(entry)

# --------------------------------
# APPLY TRANSACTION
# --------------------------------
def apply_transaction(session, tx):

    tx_id = tx["tx_id"]

    sender = tx["sender_account"]
    receiver = tx["receiver_account"]

    sender_ccy = tx["currency_from"]
    receiver_ccy = tx["currency_to"]

    gross = float(tx["gross_amount"])
    net = float(tx["net_amount"])

    fee = float(tx.get("fee", 0))

    # --------------------------------
    # SAME CURRENCY
    # --------------------------------
    if sender_ccy == receiver_ccy:

        _post(
            session,
            tx_id,
            sender,
            gross,
            "DEBIT",
            sender_ccy
        )

        _post(
            session,
            tx_id,
            receiver,
            net,
            "CREDIT",
            receiver_ccy
        )

    # --------------------------------
    # CROSS BORDER / FX
    # --------------------------------
    else:

        sender_settlement_reference = (
        f"RAILONE_settlement_reference_{sender_ccy}"
    )

        receiver_settlement_reference = (
        f"RAILONE_settlement_reference_{receiver_ccy}"
    )

        source_settlement = float(
        tx["net_source_amount"]
    )

        destination_settlement = float(
        tx["net_amount"]
    )

    # --------------------------------
    # SOURCE SIDE
    # --------------------------------

    # Sender loses full source amount
    _post(
        session,
        tx_id,
        sender,
        gross,
        "DEBIT",
        sender_ccy
    )

    # settlement_reference receives source settlement
    _post(
        session,
        tx_id,
        sender_settlement_reference,
        source_settlement,
        "CREDIT",
        sender_ccy
    )

    # Revenue receives fee
    if fee > 0:

        revenue_account = (
            f"RAILONE_REVENUE-{sender_ccy}"
        )

        _post(
            session,
            tx_id,
            revenue_account,
            fee,
            "CREDIT",
            sender_ccy
        )

    # --------------------------------
    # DESTINATION SIDE
    # --------------------------------

    # settlement_reference releases destination currency
    _post(
        session,
        tx_id,
        receiver_settlement_reference,
        destination_settlement,
        "DEBIT",
        receiver_ccy
    )

    # Receiver gets destination funds
    _post(
        session,
        tx_id,
        receiver,
        destination_settlement,
        "CREDIT",
        receiver_ccy
    )
    # --------------------------------
    # VALIDATE
    # --------------------------------
    _validate_transaction(
        session,
        tx_id
    )


# --------------------------------
# ATTESTATION / EVENT LOGGING
# --------------------------------
def record_event(session, tx_id, event_type, metadata=None):

    metadata = metadata or {}

    entry = JournalEntry(
        id=str(uuid4()),
        tx_id=tx_id,
        account_id="SYSTEM_EVENT",
        amount=0,
        entry_type=event_type,  # e.g. VERIFIED, SETTLED
        currency="N/A",
        created_at=datetime.utcnow()
    )

    session.add(entry)


# --------------------------------
# INTEGRITY CHECK
# --------------------------------
def _validate_transaction(session, tx_id):

    entries = session.query(JournalEntry).filter_by(tx_id=tx_id).all()

    currency_map = {}

    for e in entries:

        if e.currency == "N/A":
            continue  # skip system events

        if e.currency not in currency_map:
            currency_map[e.currency] = 0

        if e.entry_type == "DEBIT":
            currency_map[e.currency] -= e.amount
        else:
            currency_map[e.currency] += e.amount

    for ccy, total in currency_map.items():
        if round(total, 2) != 0:
            raise Exception(f"LEDGER_IMmirrored_available_state: {ccy} → {total}")


# --------------------------------
# GENESIS (OPTIONAL, SAFE)
# --------------------------------
def apply_genesis(session, account_id, amount):

    currency = account_id.split("-")[-1]

    # Only log genesis, do NOT mutate mirrored_available_state
    _post(session, "GENESIS", account_id, amount, "CREDIT", currency)