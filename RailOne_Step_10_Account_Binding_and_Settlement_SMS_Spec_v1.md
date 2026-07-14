# RailOne Step 10 Design Lock

## Partner institution selection, account binding, and settlement SMS

- Status: Accepted design direction; implementation pending
- Date: July 14, 2026
- Custody model: Non-custodial
- Applies to: P2P and merchant-context execution intentions

## 1. Current implementation assessment

The Step 09 prototype preserves payer and beneficiary account references inside
the signed quote and immutable UTT. It also places source and destination
institution identifiers on route candidates.

That is only a partial implementation of the intended user model:

- there is no authoritative partner-institution directory yet;
- the selected sender and receiver institutions are not both bound into the
  accepted UTT endpoint snapshot;
- the current `account_reference` can still be passed directly into a provider
  adapter instead of being resolved from an opaque institution account binding;
- route eligibility does not yet prove that every candidate begins and ends at
  the institutions selected by the users; and
- there is no settlement-triggered notification outbox yet.

Step 10 must close these gaps before the account-selection experience is called
production-grade.

## 2. Locked onboarding and execution model

### Institution selection

RailOne presents only institutions that are:

- active RailOne partners;
- available in the user's country and corridor;
- enabled for the required account role and currency;
- capable of the requested execution purpose; and
- currently permitted by policy and compliance controls.

The sender selects a participating source institution. The receiver selects or
confirms a participating destination institution. RailOne does not invent an
institution or silently substitute the user's chosen endpoint.

### Account selection

After institution authentication or attestation:

- the sender selects one eligible debit account;
- the receiver selects one eligible credit account;
- self-transfer may use two accounts owned by the same person;
- merchant contexts use merchant or branch-authorized debit bindings; and
- the institution remains the authority for account ownership, status,
  authorization, limits, and available funds.

Onboarding creates reusable institution/account bindings. Each new execution
intention selects the debit and credit bindings to use for that transaction;
RailOne must not silently reuse a default account when the user or receiver is
required to choose or confirm another binding.

RailOne stores an opaque `account_binding_id`, not a raw account number, card
number, wallet number, or mobile number in the signed UTT. A secure resolver may
release the provider-required endpoint only at dispatch time and only to the
selected adapter.

### Immutable UTT endpoint snapshot

At quote acceptance, the UTT must bind these fields for each endpoint:

| Field | Sender endpoint | Receiver endpoint |
| --- | --- | --- |
| Actor | payer actor type and ID | beneficiary actor type and ID |
| Institution | selected source institution ID | selected destination institution ID |
| Account binding | opaque debit binding ID | opaque credit binding ID |
| Role | `DEBIT` | `CREDIT` |
| Account class | bank, mobile money, wallet, or approved rail endpoint | same controlled vocabulary |
| Display hint | safe masked alias | safe masked alias |
| Attestation | ownership/authority evidence reference | eligibility or participation evidence reference |

The institution directory and account binding can later become inactive,
revoked, or superseded. That mutable operational state must not rewrite an
already accepted UTT. Execution eligibility rechecks the current binding state
before every RTT.

### Route constraint

Every route candidate must satisfy:

```text
candidate.source_institution_id == UTT.payer_endpoint.institution_id
candidate.destination_institution_id == UTT.beneficiary_endpoint.institution_id
```

Intermediary institutions and rails may vary between RTT attempts. The selected
source and destination endpoints may not silently change. A user-requested
endpoint change requires a new quote and a new accepted UTT.

## 3. Canonical sequence

```text
Partner list
  -> source institution selection
  -> sender debit-account binding
  -> destination institution selection
  -> receiver credit-account binding/attestation
  -> execution intention
  -> signed quote
  -> explicit quote acceptance
  -> immutable UTT with endpoint snapshot
  -> constrained ExecutionPlan
  -> one or more RTT attempts
  -> verified provider evidence and reconciliation
  -> SETTLED projection
  -> sender and receiver notification outbox
```

RailOne remains non-custodial throughout. It requests execution from partner
institutions and never represents either selected account as a RailOne balance.

## 4. Settlement notification rule

The word `SETTLED` may appear in an SMS only when RailOne has externally
confirmed provider evidence, passed amount/reference correlation, and completed
any required reconciliation.

Do not send a settlement SMS for:

- provider `ACCEPTED_FOR_PROCESSING`;
- RTT creation or dispatch;
- a callback timeout;
- an unknown provider outcome;
- `RECONCILIATION_REQUIRED`; or
- an internal debit/credit projection without external evidence.

Notifications are created through a durable transactional outbox. The
idempotency identity is:

```text
(utt_id, settlement_evidence_id, recipient_role, channel, template_version)
```

The outbox stores an opaque contact binding, never a raw phone number. An SMS
gateway adapter resolves the contact at delivery time. A worker crash after an
uncertain gateway submission must not cause an automatic duplicate SMS unless
the gateway provides a verifiable idempotency contract.

## 5. SMS templates

### Sender — compact settlement confirmation

```text
RailOne: SETTLED. {send_currency} {send_amount} sent to {receiver_display} via {destination_institution} on {settled_at_local}. Ref {utt_short}. Fee {fee_currency} {fee_amount}.
```

Example:

```text
RailOne: SETTLED. KES 2,500.00 sent to N. Amina via M-PESA on 14 Jul 19:05 EAT. Ref UTT-7F3A91. Fee KES 25.00.
```

### Receiver — compact settlement confirmation

```text
RailOne: SETTLED. You received {receive_currency} {receive_amount} from {sender_display} into {destination_institution} {credit_account_hint} on {settled_at_local}. Ref {utt_short}.
```

Example:

```text
RailOne: SETTLED. You received KES 2,500.00 from N. Teune into M-PESA ****5678 on 14 Jul 19:05 EAT. Ref UTT-7F3A91.
```

### Merchant sender variant

```text
RailOne: SETTLED. {send_currency} {send_amount} paid by {merchant_display}/{branch_display} to {receiver_display} on {settled_at_local}. Ref {utt_short}. Fee {fee_currency} {fee_amount}.
```

### Security footer when a second SMS segment is permitted

```text
RailOne will never ask for your PIN, password or OTP by SMS.
```

## 6. Template safety rules

- Use a short UTT display reference; never expose an RTT as the customer
  transaction reference.
- Never include full account numbers, mobile numbers, national IDs, ContUIDs,
  provider credentials, or authorization references.
- Use only institution-approved display names and user-approved party aliases.
- Render money from integer minor units with the correct currency exponent.
- Render settlement time with an explicit local timezone.
- Sender and receiver amounts may differ in cross-border flows; use the accepted
  quote's correct amount for each party.
- The sender template may display the accepted customer fee. Never show internal
  routing costs.
- Template rendering is deterministic and versioned. Persist the template
  version and a hash of the rendered body for audit.
- Keep the compact variant within one SMS segment after real values are rendered
  where possible; truncate safe display aliases rather than transaction values.
- Delivery status is separate from settlement status. An SMS delivery failure
  must never regress or alter the settled transaction.

## 7. Infographic alignment notes

The uploaded infographics correctly communicate RailOne as a utility across
existing institutions, rails, senders, receivers, and merchant contexts. They
also reinforce that institutions connect and users benefit.

Before these graphics are used as technical or investor claims, revise the
following language:

- replace `guarantee completion`, `payments succeed every time`, and `always`
  with `preserves execution continuity to an explicit settled, failed, or
  reconciliation-required state`;
- describe cross-border Egypt-to-Kenya/Tanzania as roadmap architecture, since
  the current Step 09 implementation is Kenya domestic KES through one M-PESA
  sandbox adapter;
- describe AI/ML routing as a future advisory layer; the current pilot scorer is
  deterministic and integer-only, and the engine—not AI—authorizes execution;
- do not present zero-knowledge settlement engines or provider certification as
  implemented unless they have passed their own release evidence; and
- use `verified provider evidence and reconciliation` wherever the graphics say
  final settlement.

RailOne can promise continuity, traceability, deterministic recovery, and an
explicit final state. It must not promise that every provider can always deliver
a successful payment.

## 8. Step 10 implementation acceptance tests

1. Only active partner institutions appear for the requested corridor and role.
2. Sender and receiver account bindings belong to the selected institutions.
3. Quote and UTT contain opaque binding IDs and no raw account endpoints.
4. UTT endpoint fields cannot be mutated after acceptance.
5. Routes with different source or destination institutions are ineligible.
6. Revoked account bindings prevent a new RTT without rewriting the UTT.
7. `ACCEPTED_FOR_PROCESSING`, timeout, and reconciliation-open states create no
   settlement SMS.
8. Verified settlement evidence creates exactly one sender and one receiver
   notification record.
9. Duplicate evidence creates no duplicate notification.
10. Templates contain no full account, phone, identity, or authorization data.
11. Notification delivery failure does not alter settlement state.
12. An uncertain non-idempotent SMS submission is not automatically resent.
