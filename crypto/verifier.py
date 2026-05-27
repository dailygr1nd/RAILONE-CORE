# ==========================================
# crypto/verifier.py
# RailOne Execution Verifier
# ==========================================

import json

from nacl.signing import (
    VerifyKey
)

from nacl.encoding import (
    HexEncoder
)

from nacl.exceptions import (
    BadSignatureError
)

from crypto.keystore import (
    get_public_key
)


def verify_signature(

    institution_id,

    payload,

    signature
):

    public_key_hex = (
        get_public_key(
            institution_id
        )
    )

    if not public_key_hex:

        raise Exception(
            "PUBLIC_KEY_NOT_FOUND"
        )

    verify_key = VerifyKey(

        public_key_hex,

        encoder=HexEncoder
    )

    payload_bytes = json.dumps(

        payload,

        sort_keys=True

    ).encode()

    try:

        verify_key.verify(

            payload_bytes,

            bytes.fromhex(signature)
        )

        return True

    except BadSignatureError:

        return False