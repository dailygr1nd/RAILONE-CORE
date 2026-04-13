# routing.py

# =====================================
# ROUTE CONFIGURATION
# =====================================
ROUTES = [
    {"name": "BANK_RAIL", "type": "BANK", "speed": 2, "fee": 0},
    {"name": "PSP_RAIL", "type": "PSP", "speed": 1, "fee": 0},
    {"name": "LEGACY_BANK", "type": "LEGACY_BANK", "speed": 3, "fee": 2},
    {"name": "CROSS_BORDER_PSP", "type": "CROSS_PSP", "speed": 2, "fee": 1}
]

# =====================================
# RAIL CLASSIFIER
# =====================================
def classify_rail(account_string):
    if not account_string:
        return None

    rail_type = account_string.split("-", 1)[0]

    if rail_type in ["BANK_TZ", "BANK_KE", "BANK_UG"]:
        return "BANK"

    if rail_type == "PSP" or rail_type.startswith("WLT"):
        return "PSP"

    if rail_type == "LEGACY_BANK":
        return "LEGACY_BANK"

    if rail_type == "CROSS_PSP":
        return "CROSS_PSP"

    return rail_type

# =====================================
# ROUTE SCORING
# =====================================
def score_route(route, is_cross_border, debit_rail):
    score = 0

    # Faster rails are better
    score += max(0, 5 - route.get("speed", 3))

    # Lower fee better
    score += max(0, 5 - route.get("fee", 2))

    # Prefer same rail family
    if route["type"] == debit_rail:
        score += 4

    # Cross-border preference
    if is_cross_border:
        if route["type"] in ["CROSS_PSP", "LEGACY_BANK"]:
            score += 5
    else:
        if route["type"] in ["BANK", "PSP"]:
            score += 5

    return score

# =====================================
# INTELLIGENT ROUTER
# =====================================
def auto_route(
    amount,
    sender,
    bank_balances,
    currency,
    destination,
    is_cross_border=False,
    debit_account=None
):
    """
    Select the best route automatically.

    Parameters:
        amount: float
        sender: dict with user info
        bank_balances: dict of sender's accounts & balances
        currency: str (KES, TZS, UGX, USD)
        destination: str (KE, TZ, UG, US)
        is_cross_border: bool
        debit_account: str (rail prefix + account ID)

    Returns:
        dict: route info including selected rail
    """
    debit_rail = classify_rail(debit_account)

    candidate_routes = []

    # =========================
    # LOCAL LOGIC
    # =========================
    if not is_cross_border:
        for route in ROUTES:
            if route["type"] in ["BANK", "PSP"]:
                candidate_routes.append(route)
    # =========================
    # CROSS-BORDER LOGIC
    # =========================
    else:
        for route in ROUTES:
            if route["type"] in ["LEGACY_BANK", "CROSS_PSP"]:
                candidate_routes.append(route)
            # fallback: allow local bank if no PSP available
            if route["type"] == "BANK":
                candidate_routes.append(route)

    if not candidate_routes:
        return None

    # Score each candidate route
    scored = [(route, score_route(route, is_cross_border, debit_rail))
              for route in candidate_routes]

    # Pick the highest score
    best_route = sorted(scored, key=lambda x: x[1], reverse=True)[0][0].copy()

    best_route.update({
        "cross_border": is_cross_border,
        "currency": currency,
        "destination": destination,
        "debit_rail": debit_rail
    })

    return best_route