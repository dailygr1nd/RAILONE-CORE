# ==============================
# trust_registry.py (ADVANCED + SAFE)
# ==============================

from datetime import datetime, timedelta


class TrustRegistry:
    """
    Global trust layer:
    - manages institution identities
    - handles key lifecycle (active, expired, revoked)
    - supports rotation + historical verification
    """

    _registry = {}

    KEY_TTL_DAYS = 90

    # --------------------------------
    # REGISTER / ONBOARD
    # --------------------------------
    @staticmethod
    def register_institution(institution_id: str, public_key):
        now = datetime.utcnow()

        if institution_id in TrustRegistry._registry:
            print(f"⚠️ Institution already exists: {institution_id}")
            return

        TrustRegistry._registry[institution_id] = {
            "keys": [
                {
                    "public_key": public_key,
                    "created_at": now,
                    "expires_at": now + timedelta(days=TrustRegistry.KEY_TTL_DAYS),
                    "status": "ACTIVE",
                    "version": 1
                }
            ],
            "status": "ACTIVE"
        }

        print(f"✅ Institution onboarded: {institution_id}")

    # --------------------------------
    # GET ACTIVE KEY (STRICT)
    # --------------------------------
    @staticmethod
    def get_public_key(institution_id: str):
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            raise Exception("UNKNOWN_INSTITUTION")

        if inst["status"] != "ACTIVE":
            raise Exception("INSTITUTION_INACTIVE")

        now = datetime.utcnow()

        # return latest valid active key
        for key in reversed(inst["keys"]):
            if key["status"] == "ACTIVE":
                if key["expires_at"] < now:
                    key["status"] = "EXPIRED"
                    continue
                return key["public_key"]

        raise Exception("NO_VALID_ACTIVE_KEY")

    # --------------------------------
    # ROTATE KEY
    # --------------------------------
    @staticmethod
    def rotate_key(institution_id: str, new_public_key):
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            raise Exception("UNKNOWN_INSTITUTION")

        now = datetime.utcnow()

        # expire old keys
        for key in inst["keys"]:
            if key["status"] == "ACTIVE":
                key["status"] = "EXPIRED"

        version = len(inst["keys"]) + 1

        inst["keys"].append({
            "public_key": new_public_key,
            "created_at": now,
            "expires_at": now + timedelta(days=TrustRegistry.KEY_TTL_DAYS),
            "status": "ACTIVE",
            "version": version
        })

        print(f"🔄 Key rotated for {institution_id} (v{version})")

    # --------------------------------
    # VERIFY SUPPORT (CRITICAL)
    # --------------------------------
    @staticmethod
    def get_all_keys(institution_id: str):
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            return []

        return inst["keys"]

    # --------------------------------
    # VERIFY AGAINST ALL VALID KEYS
    # --------------------------------
    @staticmethod
    def get_valid_public_keys(institution_id: str):
        """
        Used for signature verification across rotated keys
        """
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            return []

        now = datetime.utcnow()

        valid_keys = []

        for key in inst["keys"]:
            if key["status"] == "ACTIVE" and key["expires_at"] > now:
                valid_keys.append(key["public_key"])

        return valid_keys

    # --------------------------------
    # INSTITUTION CONTROL
    # --------------------------------
    @staticmethod
    def deactivate_institution(institution_id: str):
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            raise Exception("UNKNOWN_INSTITUTION")

        inst["status"] = "INACTIVE"

        print(f"⛔ Institution deactivated: {institution_id}")

    @staticmethod
    def activate_institution(institution_id: str):
        inst = TrustRegistry._registry.get(institution_id)

        if not inst:
            raise Exception("UNKNOWN_INSTITUTION")

        inst["status"] = "ACTIVE"

        print(f"✅ Institution activated: {institution_id}")