from institution_base import InstitutionBase

class PSPKenya(InstitutionBase):

    def verify_funds(self, account, amount):
        self.simulate_latency()

        if self.get_balance(account) >= amount:
            return {
                "status": "OK",
                "attestation": self.sign_attestation("tx_hash", "FUNDS_AVAILABLE")
            }
        return {"status": "REJECTED"}

    def reserve_funds(self, account, amount):
        self.simulate_latency()

        super().reserve_funds(account, amount)

        return {
            "status": "RESERVED",
            "attestation": self.sign_attestation("tx_hash", "FUNDS_RESERVED")
        }

    def release_funds(self, account, amount):
        super().release_funds(account, amount)

    def receive_funds(self, account, amount):
        self.credit(account, amount)

        return {
            "status": "SETTLED",
            "attestation": self.sign_attestation("tx_hash", "SETTLED")
        }