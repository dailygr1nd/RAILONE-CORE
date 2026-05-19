# ==============================
# identity/zk_sd.py
# RailOne ZK-SD Engine
# ==============================

import hashlib
import json


# ==========================================
# GENERATE DISCLOSURE PROOF
# ==========================================
def generate_disclosure_proof(

    continuity_uid,

    disclosure_type,

    disclosure_payload
):

    payload = {

        "continuity_uid":
            continuity_uid,

        "disclosure_type":
            disclosure_type,

        "payload":
            disclosure_payload
    }

    encoded = json.dumps(
        payload,
        sort_keys=True
    )

    proof_hash = hashlib.sha256(
        encoded.encode()
    ).hexdigest()

    return {

        "continuity_uid":
            continuity_uid,

        "disclosure_type":
            disclosure_type,

        "zk_proof_hash":
            proof_hash
    }


# ==========================================
# VERIFY DISCLOSURE PROOF
# ==========================================
def verify_disclosure_proof(

    disclosure_payload,

    zk_proof_hash
):

    encoded = json.dumps(

        disclosure_payload,

        sort_keys=True
    )

    calculated = hashlib.sha256(
        encoded.encode()
    ).hexdigest()

    return calculated == zk_proof_hash