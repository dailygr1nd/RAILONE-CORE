"""Explicitly gated localhost-only smoke server for Step 08.

This uses in-memory keys and stores and is never a pilot deployment profile.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


def main() -> None:
    if os.environ.get("RAILONE_ALLOW_IN_MEMORY_DEV_SERVER") != "1":
        raise RuntimeError(
            "refusing in-memory API startup; set "
            "RAILONE_ALLOW_IN_MEMORY_DEV_SERVER=1 for localhost smoke testing"
        )
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("install Step 08 with the [api] extra") from exc

    from railone_api import (
        AccessTokenService,
        ActorScopes,
        AuthenticatedRequestGuard,
        InMemoryApiAuditStore,
        InMemoryRateLimitStore,
        PrincipalType,
        RailOneApiFacade,
    )
    from railone_api.http import create_app
    from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
    from railone_crypto.signature_service import SignatureService
    from railone_history import InMemoryTransactionHistoryStore, TransactionHistoryService
    from railone_projection import InMemoryProviderOutcomeProjectionStore

    now = datetime.now(timezone.utc)
    keys = InMemoryEd25519KeyProvider()
    keys.generate(
        key_id="DEV:access", owner_id="DEV", purpose=KeyPurpose.ACCESS_TOKEN_SIGNING,
        not_before=now - timedelta(minutes=1), not_after=now + timedelta(hours=1),
    )
    keys.generate(
        key_id="DEV:audit", owner_id="DEV", purpose=KeyPurpose.API_AUDIT_SIGNING,
        not_before=now - timedelta(minutes=1), not_after=now + timedelta(hours=1),
    )
    tokens = AccessTokenService(keys=keys, issuer="railone-local-dev")
    token = tokens.issue(
        principal_id="DEV-MERCHANT-USER", principal_type=PrincipalType.HUMAN,
        scopes=ActorScopes(merchant_ids=("MER002",), branch_ids=("BR001",)),
        key_id="DEV:access", at=now,
    )
    guard = AuthenticatedRequestGuard(
        tokens=tokens, rate_limits=InMemoryRateLimitStore(),
        audits=InMemoryApiAuditStore(), signatures=SignatureService(keys),
        audit_signing_key_id="DEV:audit",
    )
    facade = RailOneApiFacade(
        guard=guard,
        history=TransactionHistoryService(InMemoryTransactionHistoryStore()),
        outcomes=InMemoryProviderOutcomeProjectionStore(),
    )
    print("Local-only bearer token (15 minutes):")
    print(token)
    uvicorn.run(
        create_app(facade=facade, expose_docs=True),
        host="127.0.0.1", port=8080, reload=False,
    )


if __name__ == "__main__":
    main()
