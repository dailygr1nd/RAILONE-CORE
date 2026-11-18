# AviaOS merchant sandbox intake

The sandbox operator enables the merchant endpoint by passing
`enable_avia_merchant=True` to `authenticated_p2p_facade`. This serves both
channels on one API. The default composition serves the individual P2P routes.

AviaOS posts to `/v1/avia/merchant/utts` with its bearer token and
`Idempotency-Key`. The JSON body contains exactly `operation`, `branch_id`,
`origin_intent_id`, and `signed_quote`. The response returns the UTT ID,
acceptance status, and replay flag. Acceptance records the authenticated
service principal. AviaOS owns its human operator approval workflow.

The trusted token issuer provisions a MERCHANT_SERVICE credential for one
merchant, its authorized branches, an explicit avia.PAY_SUPPLIER or
avia.BRANCH_FUND_TRANSFER permission, and the endpoint grants derived by
railone_api.avia.branch_permission. A debit grant binds the source branch
to the institution and account binding in the signed quote. Branch transfers
also require a credit grant for the distinct destination branch and endpoint.
Supplier payments require a signed SUPPLIER beneficiary. The token issuer
must verify branch and account ownership before assigning grants.

Individual P2P clients use /v1/bilateral/p2p. The human payer and receiver
sign ETK-S and ETK-R respectively; the scoped delegation profile supports a
mandated destination institution. The payer submits the verified pair for UTT
creation. Clients obtain their signed quotes, identities and keys through
separately provisioned services. Neither endpoint gives clients adapter access.
