# Delegated receiver acceptance in the institutional sandbox

A beneficiary may sign a version 1 receiving mandate authorizing one destination
institution to accept inbound transfers to one verified account binding, in one
currency, up to a limit per transfer and before an expiry. A mandate can cover
multiple transfers. The beneficiary signs the grant before the sender signs
ETK-S. A trusted operator provisions the signed grant in PostgreSQL and can
revoke it there. This sandbox includes no public enrollment or revocation API.

The institution signs ETK-R for the exact sender ETK-S and quote, with mode
BENEFICIARY_PREAUTHORIZED and receiver_confirmed false. The authenticated
receiver verification route checks the partner scope and signatures. UTT
creation requires the payer principal. At acceptance PostgreSQL locks the
registered grant, checks its contents, status and deadlines and commits the
bilateral evidence, UTT and idempotency record together. A committed revocation
blocks new acceptance. A later revocation preserves previously accepted UTTs.
An absent beneficiary or passive credit supplies no delegation authority.

Run the disposable sandbox with --http-bilateral --delegated and any of
--scenario accepted, --scenario timeout or --scenario crash. Each run requires
--reset-disposable-db and rebuilds the disposable schemas. Omitting --delegated
exercises direct beneficiary acceptance.
