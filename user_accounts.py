import random

ACCOUNTS = {}

# --------------------------
# BANKS PER JURISDICTION
# --------------------------
BANKS = {
    "TZ": "BANK_TZ",
    "KE": "BANK_KE",
    "UG": "BANK_UG"
}

# --------------------------
# PSP MOBILE MONEY
# --------------------------
PSP_WALLETS = {
    "TZ": ["PSP_MPESA_TZ", "PSP_AIRTEL_TZ"],
    "KE": ["PSP_MPESA_KE", "PSP_AIRTEL_KE"],
    "UG": ["PSP_AIRTEL_UG"]
}

# --------------------------
# SMOVE IMT WALLET (NEW)
# --------------------------
SMOVE_CURRENCIES = ["USD", "EUR", "GBP", "NGN", "ZAR", "EGP"]

# --------------------------
# ACCOUNT GENERATION
# --------------------------
def generate_accounts(nid, country):
    if nid in ACCOUNTS:
        return ACCOUNTS[nid]

    user_accounts = {}

    # ---------------- BANK ACCOUNTS ----------------
    bank = BANKS.get(country)
    if bank:
        user_accounts[bank] = {}

        for _ in range(2):
            acc_id = f"{bank}-ACC-{country}-{random.randint(1000,9999)}"
            currency = {"KE": "KES", "TZ": "TZS", "UG": "UGX"}[country]
            balance = random.randint(100_000, 5_000_000)

            user_accounts[bank][acc_id] = {
                "currency": currency,
                "balance": balance
            }

    # ---------------- PSP MOBILE MONEY ----------------
    user_accounts["PSP"] = {}

    for psp in PSP_WALLETS.get(country, []):
        acc_id = f"{psp}-{random.randint(1000,9999)}"
        currency = {"KE": "KES", "TZ": "TZS", "UG": "UGX"}[country]
        balance = random.randint(50_000, 2_000_000)

        user_accounts["PSP"][acc_id] = {
            "currency": currency,
            "balance": balance
        }

    # ---------------- SMOVE WALLET (IMT RAIL) ----------------
    user_accounts["SMOVE_WALLET"] = {}

    for ccy in SMOVE_CURRENCIES:
        acc_id = f"SMV-{ccy}-{random.randint(1000,9999)}"
        balance = random.randint(50, 10_000)

        user_accounts["SMOVE_WALLET"][acc_id] = {
            "currency": ccy,
            "balance": balance
        }

    ACCOUNTS[nid] = user_accounts
    return user_accounts


# --------------------------
# HELPERS
# --------------------------
def get_accounts(nid, rail_type):
    return ACCOUNTS.get(nid, {}).get(rail_type, {})


def get_user_balance(nid, rail_type):
    accounts = ACCOUNTS.get(nid, {}).get(rail_type, {})
    if not accounts:
        return None
    return max(a["balance"] for a in accounts.values())


# --------------------------
# CORE LEDGER ACTIONS
# --------------------------
def debit_account(nid, account_id, amount):
    user = ACCOUNTS.get(nid, {})

    for rail, accounts in user.items():
        if account_id in accounts:
            if accounts[account_id]["balance"] < amount:
                return False, "INSUFFICIENT_FUNDS"

            accounts[account_id]["balance"] -= amount
            return True, accounts[account_id]["balance"]

    return False, "ACCOUNT_NOT_FOUND"


def credit_account(nid, account_id, amount):
    user = ACCOUNTS.get(nid, {})

    for rail, accounts in user.items():
        if account_id in accounts:
            accounts[account_id]["balance"] += amount
            return True, accounts[account_id]["balance"]

    return False, "ACCOUNT_NOT_FOUND"


def get_account_balance(nid, account_id):
    user = ACCOUNTS.get(nid, {})

    for _, accounts in user.items():
        if account_id in accounts:
            return accounts[account_id]["balance"]

    return None