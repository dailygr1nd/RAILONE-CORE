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

from execution.event_models import (
    ExecutionEvent
)

from execution.checkpoint_models import (
    ExecutionCheckpoint
)
from execution.replay_models import *

from execution.replay_models import (
    ExecutionReplay
)


print("\n🔧 Creating RailOne tables...")

Base.metadata.create_all(bind=engine)

print("✅ Schema initialized")