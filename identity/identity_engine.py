# ==============================
# identity_engine.py
# RailOne Identity Continuity Engine
# ==============================

import uuid


# --------------------------------
# PROTOCOL NAMESPACE
# --------------------------------
PROTOCOL_NAMESPACE = "R1"


# --------------------------------
# DEFAULT CORRIDOR
# --------------------------------
DEFAULT_CORRIDOR = "EA"


# --------------------------------
# TRUST TIER MAP
# --------------------------------
TRUST_TIERS = {

    "UNVERIFIED": "T0",

    "BASIC_KYC": "T1",

    "GOV_VERIFIED": "T2",

    "BIOMETRIC": "T3",

    "ENHANCED_COMPLIANCE": "T4",

    "INSTITUTIONAL": "T5"
}


# --------------------------------
# GENERATE CONTINUITY UID
# --------------------------------
def generate_continuity_uid():

    return uuid.uuid4().hex[:8].upper()


# --------------------------------
# GENERATE RIG
# Immutable Genesis Anchor
# --------------------------------
def generate_rig(uid):

    return f"RIG-{uid}"


# --------------------------------
# GENERATE RIO
# Canonical Identity Object
# --------------------------------
def generate_rio(uid):

    return f"RIO-{uid}"


# --------------------------------
# GENERATE RIV
# Identity Revision Object
# --------------------------------
def generate_riv(
    uid,
    revision=1
):

    return f"RIV-{uid}-R{revision}"


# --------------------------------
# GENERATE PUBLIC RAILONE ID
# --------------------------------
def generate_railone_id(

    corridor=DEFAULT_CORRIDOR,

    trust_tier="T2",

    revision=1
):

    uid = generate_continuity_uid()

    railone_id = (

        f"{PROTOCOL_NAMESPACE}-"

        f"{corridor}-"

        f"{trust_tier}-"

        f"{uid}-"

        f"R{revision}"
    )

    return {

        "railone_id": railone_id,

        "uid": uid,

        "rig": generate_rig(uid),

        "rio": generate_rio(uid),

        "riv": generate_riv(
            uid,
            revision
        ),

        "trust_tier": trust_tier,

        "revision": revision
    }