# user_accounts.py
import random

# Global storage of all users’ accounts
ACCOUNTS = {}

# --------------------------
# BANKS PER JURISDICTION
# --------------------------
BANKS = {
    "TZ": "BANK_TZ",
    "KE": "BANK_KE",
    "UG": "LEGACY_BANK"  # Use legacy for UG accounts
}

# --------------------------
# PSP / Mobile Money
# --------------------------
PSP_WALLETS = {
    "TZ": ["PSP-MPESA", "PSP-AIRTEL"],
    "KE": ["PSP-MPESA", "PSP-AIRTEL"],
    "UG": ["PSP-AIRTEL"]
}

# --------------------------
# USER ACCOUNT CREATION
# --------------------------
def generate_accounts(nid, country):
    """Generate accounts for a user in a given jurisdiction."""
    if nid in ACCOUNTS:
        return ACCOUNTS[nid]

    user_accounts = {}

    # BANK ACCOUNTS
    local_bank = BANKS.get(country)
    if local_bank:
        user_accounts[local_bank] = {}
        for i in range(2):
            acc_id = f"{local_bank[:3]}-BAN-{country}-{random.randint(100,999)}"
            balance = random.randint(100_000, 5_000_000)
            currency = {"TZ": "TZS", "KE": "KES", "UG": "UGX"}[country] if country != "UG" else "UGX"
            user_accounts[local_bank][acc_id] = {"currency": currency, "balance": balance}

    # LEGACY BANK USD ACCOUNT
    user_accounts["LEGACY_BANK"] = {}
    acc_id = f"LEG-INT-USD-{random.randint(100,999)}"
    user_accounts["LEGACY_BANK"][acc_id] = {"currency": "USD", "balance": random.randint(500, 5000)}

    # PSP MOBILE MONEY
    user_accounts["PSP"] = {}
    for psp in PSP_WALLETS.get(country, []):
        acc_id = f"{psp}-{country}-{random.randint(100,999)}"
        currency_map = {"PSP-MPESA": {"KE": "KES","TZ": "TZS"}, "PSP-AIRTEL": {"KE": "KES","TZ":"TZS","UG":"UGX"}}
        currency = currency_map[psp][country]
        balance = random.randint(50_000, 5_000_000)
        user_accounts["PSP"][acc_id] = {"currency": currency, "balance": balance}

    # WALLET / FAILURE RAIL
    user_accounts["WALLET"] = {}
    acc_id = f"WLT-{random.randint(100,999)}"
    user_accounts["WALLET"][acc_id] = {"currency": "USD", "balance": random.randint(100, 800)}

    ACCOUNTS[nid] = user_accounts
    return user_accounts

# --------------------------
# HELPER FUNCTIONS
# --------------------------
def get_accounts(nid, rail_type):
    """Return the account dict for a given rail_type and user."""
    return ACCOUNTS.get(nid, {}).get(rail_type, {})

def get_user_balance(nid, rail_type):
    """Return the max balance across accounts in a rail_type for a user."""
    accounts = ACCOUNTS.get(nid, {}).get(rail_type, {})
    if not accounts:
        return None
    return max(acc["balance"] for acc in accounts.values())


# --------------------------
# BALANCE UPDATE FUNCTIONS
# --------------------------
def debit_account(nid, account_id, amount):
    """Debit a specific account if funds are sufficient."""
    user_accounts = ACCOUNTS.get(nid, {})

    for rail_type, accounts in user_accounts.items():
        if account_id in accounts:
            current_balance = accounts[account_id]["balance"]

            if current_balance < amount:
                return False, "Insufficient funds"

            accounts[account_id]["balance"] -= amount
            return True, accounts[account_id]["balance"]

    return False, "Account not found"


def credit_account(nid, account_id, amount):
    """Credit a specific account."""
    user_accounts = ACCOUNTS.get(nid, {})

    for rail_type, accounts in user_accounts.items():
        if account_id in accounts:
            accounts[account_id]["balance"] += amount
            return True, accounts[account_id]["balance"]

    return False, "Account not found"


def get_account_balance(nid, account_id):
    """Return exact balance for one account."""
    user_accounts = ACCOUNTS.get(nid, {})

    for rail_type, accounts in user_accounts.items():
        if account_id in accounts:
            return accounts[account_id]["balance"]

    return None