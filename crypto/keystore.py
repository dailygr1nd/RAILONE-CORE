# ==========================================
# crypto/keystore.py
# RailOne Cryptographic Keystore
# ==========================================

import os
import json

from pathlib import Path


KEYSTORE_DIR = Path(
    "crypto/keys"
)

KEYSTORE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# KEY PATHS
# ==========================================
def get_key_path(
    institution_id
):

    return (
        KEYSTORE_DIR
        /
        f"{institution_id}.json"
    )


# ==========================================
# STORE KEYPAIR
# ==========================================
def store_keypair(

    institution_id,

    private_key,

    public_key,

    metadata=None
):

    key_path = get_key_path(
        institution_id
    )

    payload = {

        "institution_id":
            institution_id,

        "private_key":
            private_key,

        "public_key":
            public_key,

        "metadata":
            metadata or {}
    }

    with open(
        key_path,
        "w"
    ) as f:

        json.dump(
            payload,
            f,
            indent=4
        )


# ==========================================
# LOAD KEYPAIR
# ==========================================
def load_keypair(
    institution_id
):

    key_path = get_key_path(
        institution_id
    )

    if not key_path.exists():

        return None

    with open(
        key_path,
        "r"
    ) as f:

        return json.load(f)


# ==========================================
# PUBLIC KEY LOOKUP
# ==========================================
def get_public_key(
    institution_id
):

    keypair = load_keypair(
        institution_id
    )

    if not keypair:

        return None

    return keypair.get(
        "public_key"
    )


# ==========================================
# PRIVATE KEY LOOKUP
# ==========================================
def get_private_key(
    institution_id
):

    keypair = load_keypair(
        institution_id
    )

    if not keypair:

        return None

    return keypair.get(
        "private_key"
    )


# ==========================================
# KEY EXISTS
# ==========================================
def key_exists(
    institution_id
):

    return (
        get_key_path(
            institution_id
        )
        .exists()
    )