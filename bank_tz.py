from institution_base import InstitutionBase

class BankTanzania(InstitutionBase):

    def verify_funds(self, account, amount):
        self.simulate_latency(0.5, 2.0)

        if self.get_balance(account) >= amount:
            return {"status": "OK"}
        return {"status": "REJECTED"}

    def receive_funds(self, account, amount):
        self.simulate_latency(0.5, 2.0)

        self.credit(account, amount)

        return {
            "status": "SETTLED",
            "attestation": self.sign_attestation("tx_hash", "SETTLED")
        }

    def provide_fx_quote(self, pair, amount):
        self.simulate_latency()

        base_rate = 18.5
        spread = 0.005

        rate = base_rate * (1 + spread)

        return {
            "pair": pair,
            "rate": rate,
            "valid_for_seconds": 5
        }