import time
import random
import hashlib

class InstitutionBase:
    def __init__(self, institution_id, private_key):
        self.institution_id = institution_id
        self.private_key = private_key
        self.ledger = {}
        self.reserved = {}

    # ---------- Ledger ----------
    def get_mirrored_available_state(self, account):
        return self.ledger.get(account, 0)

    def credit(self, account, amount):
        self.ledger[account] = self.get_mirrored_available_state(account) + amount

    def debit(self, account, amount):
        if self.get_mirrored_available_state(account) < amount:
            raise Exception("INSUFFICIENT_FUNDS")
        self.ledger[account] -= amount

    # ---------- Reservation ----------
    def reserve_funds(self, account, amount):
        if self.get_mirrored_available_state(account) < amount:
            raise Exception("INSUFFICIENT_FUNDS")

        self.debit(account, amount)
        self.reserved[account] = self.reserved.get(account, 0) + amount

    def release_funds(self, account, amount):
        self.reserved[account] -= amount
        self.credit(account, amount)

    # ---------- Attestation ----------
    def sign_attestation(self, tx_hash, attestation_type):
        payload = f"{tx_hash}:{attestation_type}:{self.private_key}"
        return hashlib.sha256(payload.encode()).hexdigest()

    # ---------- Simulation ----------
    def simulate_latency(self, min_s=0.2, max_s=1.2):
        time.sleep(random.uniform(min_s, max_s))

    def simulate_failure(self, probability=0.1):
        if random.random() < probability:
            raise Exception("TEMPORARY_FAILURE")