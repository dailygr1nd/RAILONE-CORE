import unittest
from datetime import datetime, timedelta, timezone

from railone_authority.mandates import MODE, grant, receiver_owner
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import SignatureService


class ReceivingMandateTests(unittest.TestCase):
    def test_scope_and_time_boundaries(self):
        keys = InMemoryEd25519KeyProvider()
        now = datetime.now(timezone.utc)
        keys.generate(key_id="beneficiary-key", owner_id="B", purpose=KeyPurpose.EXECUTION_SIGNING,
                      not_before=now-timedelta(days=1), not_after=now+timedelta(days=1))
        signatures = SignatureService(keys)
        arguments = dict(beneficiary="B", institution="I", account_binding_id="A", currency="TZS",
                         max_receive_minor=100, issued_at=now, expires_at=now+timedelta(minutes=1),
                         signing_key_id="beneficiary-key")
        terms = {"beneficiary": {"actor_id": "B", "endpoint": {"institution_id": "I", "account_binding_id": "A"}},
                 "receive_amount_minor": 100, "currency_to": "TZS"}
        epoch = int(now.timestamp())

        def check(**changes):
            evidence = grant(signatures, **(arguments | changes))
            receiver = dict(participation_mode=MODE, receiver_confirmed=False, mandate=evidence.to_dict())
            return receiver_owner(signatures, receiver, terms, sender_epoch=epoch+2, check_epoch=epoch+4)

        self.assertEqual(check(), "I")
        for change in (dict(beneficiary="C"), dict(institution="J"), dict(account_binding_id="Z"),
                       dict(currency="KES"), dict(max_receive_minor=99),
                       dict(issued_at=now+timedelta(seconds=3)), dict(expires_at=now+timedelta(seconds=4))):
            with self.subTest(change=change), self.assertRaises(PermissionError):
                check(**change)
