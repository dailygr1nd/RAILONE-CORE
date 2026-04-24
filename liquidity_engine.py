# ==============================
# liquidity_engine.py (ROUTE-AWARE)
# ==============================

from rails_config import get_rail


def check_liquidity(route, amount):

    if not route or route.get("type") == "FAILED":
        return False, "NO_ROUTE"

    steps = route.get("steps", [])

    # --------------------------------
    # BASIC RULES
    # --------------------------------
    for step in steps:

        action = step.get("action")
        from_acc = step.get("from")
        to_acc = step.get("to")

        from_rail = get_rail(from_acc)
        to_rail = get_rail(to_acc)

        # --------------------------------
        # TRANSFER CHECK
        # --------------------------------
        if action == "TRANSFER":

            # For now, assume all rails are liquid
            continue

        # --------------------------------
        # FX CHECK (SMOVE must handle it)
        # --------------------------------
        elif action == "FX":

            if from_rail != "SMOVE":
                return False, "INVALID_FX_ROUTE"

            # FX pools will handle liquidity (we already funded them)
            continue

    return True, None