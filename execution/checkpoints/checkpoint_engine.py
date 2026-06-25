# ==============================
# execution/checkpoint_engine.py
# RailOne Deterministic
# Execution Snapshot Engine
# ==============================

import hashlib
import json

from ledger.db import SessionLocal

from execution.checkpoints.checkpoint_models import (
    ExecutionCheckpoint
)


# ==========================================
# HASH EXECUTION SNAPSHOT
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
# CREATE EXECUTION CHECKPOINT
# ==========================================
def create_checkpoint(

    utt_id,

    checkpoint_state,

    snapshot,

    rtt_id=None,

    continuity_uid=None,

    lineage_parent=None,

    replay_generation=0,

    provider=None,

    provider_reference=None
):

    session = SessionLocal()

    try:

        integrity_hash = (

            hash_snapshot(snapshot)
        )

        checkpoint = (

            ExecutionCheckpoint(

    utt_id=utt_id,

    rtt_id=rtt_id,

    continuity_uid=
        continuity_uid,

    checkpoint_state=
        checkpoint_state,

    lineage_parent=
        lineage_parent,

    replay_generation=
        replay_generation,

    execution_snapshot=
        snapshot,

    provider=
        provider,

    provider_reference=
        provider_reference,

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