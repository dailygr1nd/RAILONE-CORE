import random
from ledger.db import SessionLocal
from ledger.ledger_service import apply_genesis



# ==============================
# bootstrap.py
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_genesis

from ledger.ledger_service import apply_genesis
from rails_config import RAILS
from liquidity_pools import POOLS
from ledger.db import SessionLocal


def bootstrap_settlement_accounts():

    session = SessionLocal()

    # Settlement accounts
    for rail in RAILS.values():
        acc = rail["settlement_account"]
        apply_genesis(session, acc, 1_000_000)

    # Liquidity pools
    for pool in POOLS.values():
        apply_genesis(session, pool, 5_000_000)

    session.commit()
    session.close()

    print("✅ Settlement + Liquidity bootstrapped")


def bootstrap_fx_pools():

    session = SessionLocal()

    pools = [
        "FX_POOL-KES",
        "FX_POOL-TZS",
        "FX_POOL-UGX"
    ]

    for p in pools:
        apply_genesis(session, p, 1_000_000)

    session.commit()
    session.close()

    print("✅ FX Pools bootstrapped")

import random

def bootstrap_user_accounts(railone_id, country="KE"):

    session = SessionLocal()
    accounts = []

    # -----------------------------
    # LOCAL RAILS (REALISTIC)
    # -----------------------------
    if country == "KE":
        accounts += [
            f"MPESA-{railone_id}-KES",
            f"AIRTEL-{railone_id}-KES",
            f"BANK_KE-{railone_id}-KES",
        ]

    elif country == "TZ":
        accounts += [
            f"MPESA-{railone_id}-TZS",
            f"AIRTEL-{railone_id}-TZS",
            f"BANK_TZ-{railone_id}-TZS",
        ]

    elif country == "UG":
        accounts += [
            f"AIRTEL-{railone_id}-UGX",
            f"BANK_UG-{railone_id}-UGX",
        ]

    # -----------------------------
    # SMOVE MULTI-CURRENCY WALLET
    # -----------------------------
    smove_currencies = ["USD", "GBP", "NGN", "ZAR", "EGP"]
    selected = random.sample(smove_currencies, 2)

    for ccy in selected:
        accounts.append(f"SMOVE-{railone_id}-{ccy}")

    # -----------------------------
    # FUND
    # -----------------------------
    for acc in accounts:
        apply_genesis(session, acc, 100000.0)

    session.commit()
    session.close()

    return accounts