import hashlib


class ReplayGuard:

    @staticmethod
    def generate_execution_hash(payload: dict):

        canonical = str(sorted(payload.items()))

        return hashlib.sha256(
            canonical.encode()
        ).hexdigest()