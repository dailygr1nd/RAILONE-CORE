# ==============================
# liquidity_engine.py (UPGRADED)
# ==============================

from ledger.models import Account
from liquidity_pools import POOLS


LOW_THRESHOLD = 0.2   # 20%
CRITICAL_THRESHOLD = 0.1  # 10%


def get_pool_balance(session, currency):
    pool = POOLS[currency]
    acc = session.query(Account).filter_by(id=pool).first()
    return acc.balance if acc else 0


def get_liquidity_pressure(session, currency):

    balance = get_pool_balance(session, currency)

    # Assume bootstrap = 5M (you can store this later)
    capacity = 5_000_000

    ratio = balance / capacity

    if ratio < CRITICAL_THRESHOLD:
        return "CRITICAL"

    elif ratio < LOW_THRESHOLD:
        return "LOW"

    return "NORMAL"