# ==============================
# execution/checkpoint_engine.py
# RailOne Checkpoint Engine
# ==============================

import hashlib
import json

from db import SessionLocal

from execution.checkpoint_models import (
    ExecutionCheckpoint
)


# ==========================================
# HASH SNAPSHOT
# ==========================================
def hash_snapshot(snapshot):

    encoded = json.dumps(
        snapshot,
        sort_keys=True
    ).encode()

    return hashlib.sha256(
        encoded
    ).hexdigest()


# ==========================================
# CREATE CHECKPOINT
# ==========================================
def create_checkpoint(

    tx_id,

    checkpoint_state,

    snapshot,

    continuity_id=None,

    replay_generation=0
):

    session = SessionLocal()

    try:

        integrity_hash = (
            hash_snapshot(snapshot)
        )

        checkpoint = (
            ExecutionCheckpoint(

                tx_id=tx_id,

                continuity_id=
                    continuity_id,

                checkpoint_state=
                    checkpoint_state,

                replay_generation=
                    replay_generation,

                execution_snapshot=
                    snapshot,

                integrity_hash=
                    integrity_hash
            )
        )

        session.add(checkpoint)

        session.commit()

        print(
            f"💾 Checkpoint saved "
            f"[{checkpoint_state}]"
        )

        return checkpoint.id

    finally:

        session.close()