# Account-binding and settlement-SMS runbook

## Institution onboarding

1. Register the institution with its approved countries, currencies, and debit
   or credit roles.
2. Keep the institution `PAUSED` until contractual, security, compliance, and
   sandbox checks pass.
3. Create account bindings only from institution-authenticated evidence.
4. Store provider-ready account endpoints in an isolated encrypted resolver,
   keyed by `institution_id + account_binding_id`.
5. Store only opaque binding IDs in RailOne contracts and databases.

## User flow

1. Show active eligible partner institutions.
2. Onboard reusable sender and receiver account bindings.
3. For each execution intention, explicitly select the debit and credit binding.
4. Issue the quote only after both selections validate.
5. At acceptance, verify the UTT contains both endpoint snapshots.
6. Before every RTT, revalidate current binding and institution status.

## Settlement notification drill

Verify these negative cases create no SMS:

- quote or UTT creation;
- provider dispatch;
- `ACCEPTED_FOR_PROCESSING`;
- callback authentication failure;
- amount/reference mismatch;
- timeout; and
- reconciliation still open.

Then process one correlated provider success. Verify:

- one signed settlement-evidence record;
- one sender and one receiver SMS record;
- no raw phone/account/identity values in either body;
- correct accepted sender amount, receiver amount, fee, UTT reference, and
  timezone; and
- duplicate callback creates no additional evidence or messages.

Run an SMS worker-crash drill from `DISPATCHING`. For a non-idempotent gateway,
the record must become `UNKNOWN` and the worker must make zero additional send
calls. Resolve unknown notification delivery operationally; never alter the
transaction's settled state.

## Production no-go conditions

- unresolved raw account endpoint in a signed quote or UTT;
- inactive institution or binding accepted for a new RTT;
- route endpoint differs from the UTT endpoint;
- SMS generated before signed settlement evidence;
- full phone, account, national ID, ContUID, or authorization reference in SMS;
- unregistered SMS sender ID or unresolved communications requirements; or
- skipped live PostgreSQL migration/concurrency gate.
