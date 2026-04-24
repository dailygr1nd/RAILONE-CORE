import random
from ledger.db import SessionLocal
from ledger.ledger_service import apply_genesis



# ==============================
# bootstrap.py
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_genesis


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

def bootstrap_user_accounts(railone_id, country="KE"):

    session = SessionLocal()
    accounts = []

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

    # SMOVE multi-currency (random selection)
    smove_currencies = ["USD", "GBP", "NGN", "ZAR", "EGP"]
    selected = random.sample(smove_currencies, 2)

    for ccy in selected:
        accounts.append(f"SMOVE-{railone_id}-{ccy}")

    # FUND
    for acc in accounts:
        apply_genesis(session, acc, 100000.0)

    session.commit()
    session.close()

    return accounts