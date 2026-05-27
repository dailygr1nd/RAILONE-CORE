# ==========================================
# crypto/signer.py
# RailOne Execution Signer
# ==========================================

import json

from nacl.signing import (
    SigningKey
)

from nacl.encoding import (
    HexEncoder
)

from crypto.keystore import (
    get_private_key
)


def sign_payload(

    institution_id,

    payload
):

    private_key_hex = (
        get_private_key(
            institution_id
        )
    )

    if not private_key_hex:

        raise Exception(
            "PRIVATE_KEY_NOT_FOUND"
        )

    signing_key = SigningKey(

        private_key_hex,

        encoder=HexEncoder
    )

    payload_bytes = json.dumps(

        payload,

        sort_keys=True

    ).encode()

    signature = signing_key.sign(
        payload_bytes
    )

    return signature.signature.hex()