# zk_sd.py
import hashlib
import random
from datetime import datetime, timezone

from identity_db import lookup_identity
from user_accounts import generate_accounts

USED_IDS = set()


# --------------------------
# HASH ENGINE
# --------------------------
def hash_str(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


# --------------------------
# KYC TIER ENGINE
# --------------------------
def generate_kyc_level():
    return random.choice(["TIER_1", "TIER_2", "TIER_3"])


# --------------------------
# RAILONE ID DISPLAY
# --------------------------
def generate_railone_id(identity_token: str) -> str:
    return identity_token[:16]


# --------------------------
# ONBOARD USER
# --------------------------

def onboard_user(name, nid, role="user"):
    print("📤 Verifying identity with national registry...")

    # --------------------------
    # VALIDATION
    # --------------------------
    if not str(nid).isdigit() or len(str(nid)) != 8:
        print("❌ Invalid ID format")
        return None

    if nid in USED_IDS:
        print("❌ ID already used in this session")
        return None

    # --------------------------
    # REGISTRY LOOKUP
    # --------------------------
    record = lookup_identity(nid, name)

    if record is None:
        print("❌ ID not found")
        return None

    if record == "NAME_MISMATCH":
        print("❌ Name does not match ID record")
        return None

    if record["status"] != "valid":
        print("❌ ID not valid")
        return None

    # --------------------------
    # HASHED IDENTITY LAYER
    # --------------------------
    identity_token = hash_str(
        f"{nid}:{record['name']}:{record['country']}"
    )

    zk_proof = hash_str(identity_token + ":ZK_ATTEST")

    railone_id = generate_railone_id(identity_token)

    # --------------------------
    # KYC ATTESTATION
    # --------------------------
    kyc_level = generate_kyc_level()

    attestation_payload = {
        "issuer": f"NATIONAL_ID_{record['country']}",
        "verified": True,
        "kyc_level": kyc_level,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    attestation_signature = hash_str(str(attestation_payload))

    # --------------------------
    # ACCOUNT GENERATION
    # --------------------------
    user_accounts = generate_accounts(
        nid=nid,
        country=record["country"]
    )

    USED_IDS.add(nid)

    print(f"✅ {role} onboarded successfully")
    print(f"🔐 RailOneID: {railone_id}")
    print(f"📄 KYC Level: {kyc_level}")

    return {
        "role": role,
        "username": railone_id,
        "railone_id": railone_id,
        "nid": nid,
        "identity_token": identity_token,
        "zk_proof": zk_proof,
        "attestation": {
            **attestation_payload,
            "signature": attestation_signature
        },
        "accounts": user_accounts
    }