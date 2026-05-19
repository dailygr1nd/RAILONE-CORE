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


print("\n🔧 Creating RailOne tables...")

Base.metadata.create_all(bind=engine)

print("✅ Schema initialized")