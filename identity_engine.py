# ==============================
# identity_engine.py
# ==============================

import uuid


def generate_railone_id():
    return "R1-" + uuid.uuid4().hex[:10].upper()