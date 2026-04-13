# zk_sd.py
import hashlib
from datetime import datetime
import random
from identity_db import lookup_identity
from user_accounts import generate_accounts

USED_IDS = set()


def hash_str(data):
    return hashlib.sha256(data.encode()).hexdigest()


def generate_kyc_level():
    return random.choice(["TIER_1", "TIER_2", "TIER_3"])


def onboard_user(role):
    print(f"\n=== {role.upper()} ONBOARDING ===")

    name = input("Enter Full Name: ").strip()
    nid = input("Enter National ID: ").strip()

    # --------------------------
    # FORMAT VALIDATION
    # --------------------------
    if not nid.isdigit() or len(nid) != 8:
        print("❌ Invalid ID format")
        return None

    if nid in USED_IDS:
        print("❌ ID already used in this session")
        return None

    print("📤 Verifying identity with national registry...")
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
    # TOKEN GENERATION
    # --------------------------
    identity_token = hash_str(nid + record["name"])
    zk_proof = hash_str(identity_token + "ZK")

    # --------------------------
    # ATTESTATION
    # --------------------------
    kyc_level = generate_kyc_level()
    attestation_payload = {
        "issuer": f"NATIONAL_ID_{record['country'].upper()}",
        "verified": True,
        "kyc_level": kyc_level,
        "timestamp": datetime.utcnow().isoformat()
    }
    attestation_signature = hash_str(str(attestation_payload))

    # --------------------------
    # ATTACH ACCOUNTS
    # --------------------------
    user_accounts = generate_accounts(nid)

    # --------------------------
    # FINALIZE USER
    # --------------------------
    USED_IDS.add(nid)
    username = f"user_{nid[-4:]}"
    print(f"✅ {role} onboarded as {username}")
    print(f"🔐 KYC Level: {kyc_level}")

    return {
        "username": username,
        "nid": nid,
        "identity_token": identity_token,
        "zk_proof": zk_proof,
        "attestation": {
            **attestation_payload,
            "signature": attestation_signature
        },
        "accounts": user_accounts  # ✅ Attach accounts here
    }