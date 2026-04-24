from ledger.db import SessionLocal
from ledger.models import Account


def check_liquidity(route_type, currency, amount):
    """
    Ensure settlement account has funds
    """

    session = SessionLocal()

    settlement_id = f"SETTLEMENT-{route_type}-{currency}"

    acc = session.query(Account).filter_by(id=settlement_id).first()

    if not acc:
        session.close()
        return False, "NO_SETTLEMENT_ACCOUNT"

    if acc.balance < amount:
        session.close()
        return False, "INSUFFICIENT_LIQUIDITY"

    session.close()
    return True, None