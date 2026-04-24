from ledger.account_service import ensure_account_exists

def bootstrap_settlement_accounts():
    rails = ["SMOVE", "BANK_KE", "BANK_UG", "BANK_TZ", "MPESA"]
    currencies = ["KES", "UGX", "TZS"]

    for rail in rails:
        for ccy in currencies:
            ensure_account_exists(
                account_id=f"SETTLEMENT-{rail}-{ccy}",
                provider=rail,
                currency=ccy,
                account_type="SETTLEMENT",
                owner_id="SYSTEM",
                balance=1_000_000
            )

    print("✅ Settlement accounts bootstrapped")