# ==============================
# tables_bootstrap.py
# ==============================

from db import Base

from ledger.db import engine


# --------------------------------
# FORCE MODEL REGISTRATION
# --------------------------------
import identity.models
import ledger.models

# ==========================================
# EXECUTION EVENT MODELS
# ==========================================

from execution.events.event_models import (
    ExecutionEvent
)

from execution.checkpoints.checkpoint_models import (
    ExecutionCheckpoint
)
from execution.continuity.replay_models import *

from execution.continuity.replay_models import (
    ExecutionReplay
)


print("\n🔧 Creating RailOne tables...")

Base.metadata.create_all(bind=engine)

print("✅ Schema initialized")