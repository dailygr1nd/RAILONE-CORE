# ==============================
# keystore.py (FILE-BASED PERSISTENCE)
# ==============================

import os
from cryptography.hazmat.primitives import serialization

KEY_DIR = "keys"


def _ensure_dir():
    if not os.path.exists(KEY_DIR):
        os.makedirs(KEY_DIR)


def save_private_key(institution_id, private_key):
    _ensure_dir()

    path = f"{KEY_DIR}/{institution_id}_private.pem"

    with open(path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )


def load_private_key(institution_id):
    path = f"{KEY_DIR}/{institution_id}_private.pem"

    if not os.path.exists(path):
        return None

    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)