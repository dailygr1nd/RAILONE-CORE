import hashlib
import json
import time
import uuid

class TransactionEnvelope:
    def __init__(self, payload: dict):
        self.tx_id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.payload = payload

        self.payload_hash = self._hash_payload(payload)

        self.state = "INITIATED"
        self.attestations = []
        self.history = []

    def _hash_payload(self, payload):
        encoded = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    # ---------- State ----------
    def set_state(self, new_state):
        self.history.append({
            "from": self.state,
            "to": new_state,
            "timestamp": time.time()
        })
        self.state = new_state

    # ---------- Attestations ----------
    def add_attestation(self, party, attestation_type, signature):
        self.attestations.append({
            "party": party,
            "type": attestation_type,
            "signature": signature,
            "timestamp": time.time()
        })

    def has_attestation(self, attestation_type):
        return any(a["type"] == attestation_type for a in self.attestations)

    def get_summary(self):
        return {
            "tx_id": self.tx_id,
            "state": self.state,
            "attestations": self.attestations,
            "history": self.history
        }