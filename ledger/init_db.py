import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))



from ledger.db import engine
from ledger.models import Base

print("🔧 Creating database tables...")

Base.metadata.create_all(bind=engine)

print("✅ Tables created successfully")