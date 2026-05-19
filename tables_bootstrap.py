# ==============================
# bootstrap.py
# ==============================

from db import Base

from ledger.db import engine


print("🔧 Creating RailOne tables...")

Base.metadata.create_all(bind=engine)

print("✅ Schema initialized")