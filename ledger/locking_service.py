from sqlalchemy.orm import Session

from ledger.models import Account


# =========================================
# RESERVE EXECUTION FUNDS
# =========================================
def reserve_execution_liquidity(
    session: Session,
    account_id: str,
    amount: float
):

    account = (
        session.query(Account)
        .filter_by(id=account_id)
        .with_for_update()
        .first()
    )

    if not account:
        return False

    available = (
        account.mirrored_available_state
        - account.execution_reservation
    )

    if available < amount:
        return False

    account.execution_reservation += amount

    return True


# =========================================
# RELEASE EXECUTION RESERVATION
# =========================================
def release_execution_reservation(
    session: Session,
    account_id: str,
    amount: float
):

    account = (
        session.query(Account)
        .filter_by(id=account_id)
        .with_for_update()
        .first()
    )

    if not account:
        return False

    if account.execution_reservation < amount:
        return False

    account.execution_reservation -= amount

    return True


# =========================================
# FINALIZE EXECUTION SETTLEMENT
# =========================================
def finalize_execution_settlement(
    session: Session,
    account_id: str,
    amount: float
):

    account = (
        session.query(Account)
        .filter_by(id=account_id)
        .with_for_update()
        .first()
    )

    if not account:
        return False

    if account.execution_reservation < amount:
        return False

    account.execution_reservation -= amount

    account.mirrored_available_state -= amount

    return True