# rules.py

def enforce_attestation(user, amount):
    if not user["attestation"]["verified"]:
        return "KYC_NOT_VERIFIED"

    kyc_level = user["attestation"]["kyc_level"]

    limits = {
        "TIER_1": 50000,
        "TIER_2": 500000,
        "TIER_3": 999999999
    }

    if amount > limits.get(kyc_level, 0):
        return f"KYC_LIMIT_EXCEEDED ({kyc_level})"

    return None