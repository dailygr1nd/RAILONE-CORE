from ledger.db import engine
from ledger.models import Base  # ensures models are loaded

def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()