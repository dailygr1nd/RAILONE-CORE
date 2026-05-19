# ==============================
# test_revision.py
# ==============================

from identity.revision_engine import (
    create_identity_revision
)

# --------------------------------
# TEST USER
# --------------------------------
continuity_uid = "81B81210"

result = create_identity_revision(

    continuity_uid=continuity_uid,

    new_trust_tier="T3",

    revision_reason="TRUST_UPGRADE"
)

print("\n✅ REVISION RESULT")

print(result)