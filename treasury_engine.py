# ==============================
# treasury_engine.py
# ==============================

from ledger.models import Account
from liquidity_pools import POOLS

TARGET_BALANCE = 5_000_000
REBALANCE_THRESHOLD = 0.3  # 30%


def get_pool(session, currency):
    pool_id = POOLS.get(currency) or POOLS.get(f"{currency}_{currency}")
    return session.query(Account).filter_by(id=pool_id).first()

def safe_pool_lookup(key):

    from liquidity_pools import POOLS

    if key in POOLS:
        return POOLS[key]

    # fallback for single currency
    pair = f"{key}_{key}"

    return POOLS.get(pair)


def needs_rebalance(session, currency):

    acc = get_pool(session, currency)

    if not acc:
        return False

    ratio = acc.balance / TARGET_BALANCE

    return ratio < REBALANCE_THRESHOLD


def rebalance_pool(session, currency):

    acc = get_pool(session, currency)

    if not acc:
        return

    deficit = TARGET_BALANCE - acc.balance

    if deficit <= 0:
        return

    # 🔥 For now: simulate refill (later connect real treasury / FX desk)
    acc.balance += deficit

    print(f"🏦 Rebalanced {currency} pool by {deficit}")