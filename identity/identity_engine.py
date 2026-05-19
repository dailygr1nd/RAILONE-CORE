import uuid
import hashlib


# =========================================================
# UID GENERATION
# =========================================================

def generate_continuity_uid():

    raw = str(uuid.uuid4())

    digest = hashlib.sha256(raw.encode()).hexdigest()

    return digest[:8].upper()


# =========================================================
# RAILONE ID
# =========================================================

def build_railone_id(

    corridor,

    trust_tier,

    continuity_uid,

    revision
):

    return (
        f"R1-"
        f"{corridor}-"
        f"{trust_tier}-"
        f"{continuity_uid}-"
        f"R{revision}"
    )


# =========================================================
# RIG
# =========================================================

def generate_rig(continuity_uid):

    return f"RIG-{continuity_uid}"


# =========================================================
# RIO
# =========================================================

def generate_rio(continuity_uid):

    return f"RIO-{continuity_uid}"


# =========================================================
# RIV
# =========================================================

def generate_riv(continuity_uid, revision):

    return f"RIV-{continuity_uid}-R{revision}"


# =========================================================
# FULL IDENTITY STACK
# =========================================================

def generate_railone_identity(

    corridor="EA",

    trust_tier="T2",

    revision=1
):

    continuity_uid = generate_continuity_uid()

    railone_id = build_railone_id(

        corridor=corridor,

        trust_tier=trust_tier,

        continuity_uid=continuity_uid,

        revision=revision
    )

    rig = generate_rig(continuity_uid)

    rio = generate_rio(continuity_uid)

    riv = generate_riv(

        continuity_uid,

        revision
    )

    return {

        "railone_id": railone_id,

        "continuity_uid": continuity_uid,

        "rig": rig,

        "rio": rio,

        "riv": riv,

        "corridor": corridor,

        "trust_tier": trust_tier,

        "revision": revision
    }