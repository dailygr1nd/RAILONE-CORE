# ==============================
# liquidity_engine.py (FIXED)
# ==============================

def get_liquidity_pressure(*args):
    """
    Accept flexible args to avoid crashes.
    Later you can tighten this.
    """
    try:
        # simple mock logic for now
        return 0.1  # low pressure
    except Exception:
        return 0.5


def check_liquidity(rail, pair, amount):
    """
    Always allow for now (to unblock system)
    Later plug real pool logic.
    """
    return True, {
        "rail": rail,
        "pair": pair,
        "available": amount * 10
    }