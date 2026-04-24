import time

# simple in-memory tracking (can later move to DB)
USER_TX_HISTORY = {}


def check_velocity(user_id):
    now = time.time()

    history = USER_TX_HISTORY.get(user_id, [])

    # keep last 60 seconds
    history = [t for t in history if now - t < 60]

    if len(history) > 5:
        return False, "VELOCITY_LIMIT_EXCEEDED"

    history.append(now)
    USER_TX_HISTORY[user_id] = history

    return True, None


def check_amount(amount):
    if amount > 1_000_000:
        return False, "AMOUNT_TOO_LARGE"
    return True, None


def run_fraud_checks(user_id, amount):
    ok, reason = check_velocity(user_id)
    if not ok:
        return ok, reason

    ok, reason = check_amount(amount)
    if not ok:
        return ok, reason

    return True, None