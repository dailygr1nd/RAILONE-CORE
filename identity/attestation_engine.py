# ==============================
# identity/attestation_engine.py
# RailOne Institutional Attestation Engine

#Institutional Trust Provenance Verification
# ==============================

import hashlib

from ledger.db import SessionLocal

from ledger.models import (
    InstitutionKey
)


class AttestationEngine:


    # ==========================================
    # VERIFY ATTESTATION
    # ==========================================
    def verify_attestation(

        self,

        continuity_uid,

        riv_id,

        attestation_type,

        payload_hash,

        signature,

        institution_id
    ):

        session = SessionLocal()

        try:

            # --------------------------------
            # ACTIVE INSTITUTION KEY
            # --------------------------------
            key = (

                session.query(InstitutionKey)

                .filter_by(

                    institution_id=
                        institution_id,

                    status="ACTIVE"
                )

                .first()
            )

            if not key:

                raise Exception(

                    f"NO_ACTIVE_KEY: "
                    f"{institution_id}"
                )

            # --------------------------------
            # RECONSTRUCT SIGNATURE
            # --------------------------------
            expected = (

                self._reconstruct_signature(

                    continuity_uid,

                    riv_id,

                    attestation_type,

                    payload_hash,

                    key.public_key
                )
            )

            # --------------------------------
            # VERIFY
            # --------------------------------
            if expected != signature:

                raise Exception(

                    f"INVALID_ATTESTATION: "
                    f"{institution_id}"
                )

            return True

        finally:

            session.close()


    # ==========================================
    # BUILD SIGNATURE
    # ==========================================
    def _reconstruct_signature(

        self,

        continuity_uid,

        riv_id,

        attestation_type,

        payload_hash,

        public_key
    ):

        payload = (

            f"{continuity_uid}:"

            f"{riv_id}:"

            f"{attestation_type}:"

            f"{payload_hash}:"

            f"{public_key}"
        )

        return hashlib.sha256(
            payload.encode()
        ).hexdigest()