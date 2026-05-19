# ==============================
# identity/replay_engine.py
# RailOne Replay-Safe Continuity Engine
# ==============================

import json

import redis


# ==========================================
# REDIS
# ==========================================
r = redis.Redis(

    host="localhost",

    port=6379,

    db=0
)


# ==========================================
# QUEUES
# ==========================================
DEAD_LETTER_QUEUE = (
    "railone:dead_letter"
)

EXECUTION_QUEUE = (
    "railone:tx_queue"
)


# ==========================================
# REPLAY FAILED EXECUTIONS
# ==========================================
def replay_failed(

    limit=10
):

    print(
        "\\n🔁 RailOne Replay Engine "
        "Starting..."
    )

    replayed = 0

    for _ in range(limit):

        raw = r.rpop(
            DEAD_LETTER_QUEUE
        )

        if not raw:
            break

        tx = json.loads(raw)

        # --------------------------------
        # REQUIRE CANONICAL EXECUTION
        # --------------------------------
        utt = tx.get("utt")

        if not utt:

            print(
                "⚠️ Missing UTT "
                "- skipping"
            )

            continue

        # --------------------------------
        # REPLAY GENERATION
        # --------------------------------
        replay_generation = tx.get(
            "replay_generation",
            0
        )

        replay_generation += 1

        tx[
            "replay_generation"
        ] = replay_generation

        # --------------------------------
        # REPLAY CONTINUITY
        # --------------------------------
        tx[
            "replayed"
        ] = True

        tx[
            "replay_safe"
        ] = True

        print(

            f"🔁 Replaying "

            f"UTT={utt} "

            f"(generation "
            f"{replay_generation})"
        )

        # --------------------------------
        # RETURN TO EXECUTION QUEUE
        # --------------------------------
        r.lpush(

            EXECUTION_QUEUE,

            json.dumps(tx)
        )

        replayed += 1

    print(

        f"✅ Replay complete: "
        f"{replayed} replayed"
    )