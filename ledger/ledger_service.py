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
# APPLY TRANSACTION (RECORD ONLY)
# --------------------------------
def apply_transaction(session, tx):

    tx_id = tx["tx_id"]

    sender = tx["sender_account"]
    receiver = tx["receiver_account"]

    sender_ccy = tx["currency_from"]
    receiver_ccy = tx["currency_to"]

    gross = tx["gross_amount"]
    net = tx["net_amount"]
    fee = tx.get("fee", 0)

    # -----------------------------
    # CORE ENTRIES (EVENT RECORDING)
    # -----------------------------
    _post(session, tx_id, sender, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, receiver, net, "CREDIT", receiver_ccy)

    if fee > 0:
        revenue_account = f"RAILONE_REVENUE-{sender_ccy}"

        _post(session, tx_id, sender, fee, "DEBIT", sender_ccy)
        _post(session, tx_id, revenue_account, fee, "CREDIT", sender_ccy)

    # -----------------------------
    # VALIDATION (STILL IMPORTANT)
    # -----------------------------
    _validate_transaction(session, tx_id)


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
            raise Exception(f"LEDGER_IMBALANCE: {ccy} → {total}")


# --------------------------------
# GENESIS (OPTIONAL, SAFE)
# --------------------------------
def apply_genesis(session, account_id, amount):

    currency = account_id.split("-")[-1]

    # Only log genesis, do NOT mutate balance
    _post(session, "GENESIS", account_id, amount, "CREDIT", currency)