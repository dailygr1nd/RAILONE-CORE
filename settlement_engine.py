class SettlementEngine:

    VALID_TRANSITIONS = {
        "INITIATED": ["VERIFIED"],
        "VERIFIED": ["FUNDS_RESERVED"],
        "FUNDS_RESERVED": ["EXECUTING", "FAILED"],
        "EXECUTING": ["SETTLED", "FAILED"],
        "SETTLED": ["FINAL"],
        "FAILED": []
    }

    REQUIRED_ATTESTATIONS = {
        "FUNDS_RESERVED": ["FUNDS_AVAILABLE"],
        "SETTLED": ["SETTLED"]
    }

    def can_transition(self, tx, new_state):
        return new_state in self.VALID_TRANSITIONS.get(tx.state, [])

    def require_attestations(self, tx, new_state):
        required = self.REQUIRED_ATTESTATIONS.get(new_state, [])
        for r in required:
            if not tx.has_attestation(r):
                raise Exception(f"MISSING_ATTESTATION: {r}")

    def advance(self, tx, new_state):
        if not self.can_transition(tx, new_state):
            raise Exception(f"INVALID_TRANSITION: {tx.state} → {new_state}")

        self.require_attestations(tx, new_state)

        tx.set_state(new_state)