# ==============================
# identity/zk_sd.py
# RailOne ZK-SD Identity Layer
# ==============================

from identity.identity_engine import generate_railone_id

import hashlib
import random

from datetime import (
    datetime,
    timezone
)

from db import SessionLocal

from identity.models import User

from ledger.account_service import (
    ensure_account_exists
)

USED_IDS = set()


# ==========================================
# HASH ENGINE
# ==========================================
def hash_str(data: str) -> str:

    return hashlib.sha256(
        data.encode()
    ).hexdigest()


# ==========================================
# KYC TIER ENGINE
# ==========================================
def generate_kyc_level():

    return random.choice([
        "T1",
        "T2",
        "T3"
    ])


# ==========================================
# ACCOUNT CREATION ENGINE
# ==========================================
def create_user_accounts(
    nid,
    railone_id
):

    wallets = [

        ("MPESA", "KES"),

        ("BANK_KE", "KES"),

        ("BANK_UG", "UGX"),

        ("BANK_TZ", "TZS"),

        ("SMOVE", "KES"),

        ("SMOVE", "UGX"),

        ("SMOVE", "TZS"),
    ]

    created_accounts = []

    for provider, ccy in wallets:

        account_id = (
            f"{provider}-"
            f"{railone_id}-"
            f"{ccy}"
        )

        ensure_account_exists(

            account_id=account_id,

            provider=provider,

            currency=ccy,

            account_type="EXTERNAL_MIRROR",

            owner_id=railone_id,

            mirrored_available_state=500000.0
        )

        created_accounts.append({

            "account_id": account_id,

            "currency": ccy,

            "provider": provider
        })

    return created_accounts


# ==========================================
# ONBOARD USER
# ==========================================
def onboard_user(
    name,
    nid,
    role="user"
):

    print(
        "📤 Verifying identity..."
    )

    # ==========================================
    # VALIDATION
    # ==========================================
    if not str(nid).isdigit():

        print("❌ Invalid ID format")
        return None

    if len(str(nid)) != 8:

        print("❌ Invalid ID length")
        return None

    # ==========================================
    # DB SESSION
    # ==========================================
    session = SessionLocal()

    try:

        # ==========================================
        # EXISTING CONTINUITY USER
        # ==========================================
        existing = (

            session.query(User)

            .filter_by(
                national_id=nid
            )

            .first()
        )

        # --------------------------------
        # REUSE EXISTING IDENTITY
        # --------------------------------
        if existing:

            print(
                "✅ Existing continuity identity found"
            )

            # ensure accounts exist
            created_accounts = create_user_accounts(
                nid=nid,
                railone_id=existing.railone_id
            )

            return {

                "role": role,

                "username":
                    existing.railone_id,

                "railone_id":
                    existing.railone_id,

                "nid":
                    existing.national_id,

                "accounts":
                    created_accounts,

                "existing":
                    True
            }

        # ==========================================
        # NEW CONTINUITY USER
        # ==========================================
        identity = generate_railone_id(

            corridor="EA",

            trust_tier="T2",

            revision=1
        )

        railone_id = identity["railone_id"]

        # ==========================================
        # IDENTITY TOKEN
        # ==========================================
        identity_token = hash_str(
            f"{nid}:{name}:EA"
        )

        zk_proof = hash_str(
            identity_token +
            ":ZK_ATTEST"
        )

        # ==========================================
        # KYC
        # ==========================================
        kyc_level = (
            generate_kyc_level()
        )

        # ==========================================
        # CREATE USER RECORD
        # ==========================================
        user = User(

            railone_id=railone_id,

            continuity_uid=identity["railone_id"]
        

            rig_id=identity[
                "rig_id"
            ],

            rio_id=identity[
                "rio_id"
            ],

            active_riv_id=identity[
                "riv_id"
            ],

            corridor="EA",

            trust_tier="T2",

            revision=1,

            full_name=name,

            national_id=nid,

            kyc_status="VERIFIED"
            )

        session.add(user)

        session.commit()

        # ==========================================
        # CREATE ACCOUNTS
        # ==========================================
        created_accounts = (
            create_user_accounts(
                nid=nid,
                railone_id=railone_id
            )
        )

        # ==========================================
        # ATTESTATION
        # ==========================================
        attestation_payload = {

            "issuer":
                "NATIONAL_ID_EA",

            "verified":
                True,

            "kyc_level":
                kyc_level,

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat()
        }

        attestation_signature = (
            hash_str(
                str(attestation_payload)
            )
        )

        USED_IDS.add(nid)

        # ==========================================
        # SUCCESS
        # ==========================================
        print(
            f"✅ {role} onboarded"
        )

        print(
            f"🔐 RailOneID: "
            f"{railone_id}"
        )

        print(
            f"📄 KYC Level: "
            f"{kyc_level}"
        )

        return {

            "role":
                role,

            "username":
                railone_id,

            "railone_id":
                railone_id,

            "nid":
                nid,

            "identity_token":
                identity_token,

            "zk_proof":
                zk_proof,

            "attestation": {

                **attestation_payload,

                "signature":
                    attestation_signature
            },

            "accounts":
                created_accounts,

            "existing":
                False
        }

    finally:

        session.close()