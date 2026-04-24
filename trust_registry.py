# ==============================
# trust_registry.py (ADVANCED)
# ==============================

from datetime import datetime, timedelta


class TrustRegistry:

    _registry = {}

    KEY_TTL_DAYS = 90

    # --------------------------------
    # REGISTER / ONBOARD
    # --------------------------------
    @staticmethod
    def register_institution(institution_id, public_key):

        now = datetime.utcnow()

        TrustRegistry._registry[institution_id] = {
            "keys": [
                {
                    "public_key": public_key,
                    "created_at": now,
                    "expires_at": now + timedelta(days=TrustRegistry.KEY_TTL_DAYS),
                    "status": "ACTIVE"
                }
            ],
            "status": "ACTIVE"
        }

        print(f"✅ Institution onboarded: {institution_id}")

    # --------------------------------
    # GET ACTIVE KEY
    # --------------------------------
    @staticmethod
    def get_public_key(institution_id):

        inst = TrustRegistry._registry.get(institution_id)

        if not inst or inst["status"] != "ACTIVE":
            raise Exception("INVALID_INSTITUTION")

        # return latest active key
        for key in reversed(inst["keys"]):
            if key["status"] == "ACTIVE":
                return key["public_key"]

        raise Exception("NO_ACTIVE_KEY")

    # --------------------------------
    # ROTATE KEY
    # --------------------------------
    @staticmethod
    def rotate_key(institution_id, new_public_key):

        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            raise Exception("UNKNOWN_INSTITUTION")

        # deactivate old key
        for key in inst["keys"]:
            key["status"] = "EXPIRED"

        now = datetime.utcnow()

        inst["keys"].append({
            "public_key": new_public_key,
            "created_at": now,
            "expires_at": now + timedelta(days=TrustRegistry.KEY_TTL_DAYS),
            "status": "ACTIVE"
        })

        print(f"🔄 Key rotated for {institution_id}")

    # --------------------------------
    # VERIFY (CHAIN COMPATIBLE)
    # --------------------------------
    @staticmethod
    def get_all_keys(institution_id):
        inst = TrustRegistry._registry.get(institution_id)
        return inst["keys"] if inst else []