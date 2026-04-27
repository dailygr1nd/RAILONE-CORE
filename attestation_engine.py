# ==============================
# attestation_engine.py
# ==============================

import hashlib
from ledger.db import SessionLocal
from ledger.models import InstitutionKey


class AttestationEngine:

    # --------------------------------
    # VERIFY SIGNATURE
    # --------------------------------
    def verify(self, tx_hash, attestation_type, signature, institution_id):

        session = SessionLocal()

        try:
            key = session.query(InstitutionKey).filter_by(
                institution_id=institution_id,
                status="ACTIVE"
            ).first()

            if not key:
                raise Exception(f"NO_ACTIVE_KEY: {institution_id}")

            expected = self._reconstruct_signature(
                tx_hash,
                attestation_type,
                key.public_key
            )

            if expected != signature:
                raise Exception(f"INVALID_SIGNATURE: {institution_id}")

            return True

        finally:
            session.close()

    # --------------------------------
    # SIMPLE HASH-BASED VERIFICATION
    # --------------------------------
    def _reconstruct_signature(self, tx_hash, attestation_type, public_key):

        payload = f"{tx_hash}:{attestation_type}:{public_key}"
        return hashlib.sha256(payload.encode()).hexdigest()