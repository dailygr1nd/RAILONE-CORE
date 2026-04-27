from institution_base import InstitutionBase

class WalletUganda(InstitutionBase):

    def verify_funds(self, account, amount):
        self.simulate_latency()
        self.simulate_failure(0.15)

        if self.get_balance(account) >= amount:
            return {"status": "OK"}
        return {"status": "REJECTED"}

    def reserve_funds(self, account, amount):
        self.simulate_latency()
        self.simulate_failure(0.2)

        super().reserve_funds(account, amount)

        return {
            "status": "RESERVED",
            "attestation": self.sign_attestation("tx_hash", "FUNDS_RESERVED")
        }

    def receive_funds(self, account, amount):
        self.simulate_latency()
        self.simulate_failure(0.1)

        self.credit(account, amount)

        return {
            "status": "SETTLED",
            "attestation": self.sign_attestation("tx_hash", "SETTLED")
        }