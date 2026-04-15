import json
import random
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

STORE_PATH = Path("accounts_store.json")
STORE_LOCK = Lock()

BANKS = {
    "TZ": "BANK_TZ",
    "KE": "BANK_KE",
    "UG": "BANK_UG",
}

PSP_WALLETS = {
    "TZ": ["PSP_MPESA_TZ", "PSP_AIRTEL_TZ"],
    "KE": ["PSP_MPESA_KE", "PSP_AIRTEL_KE"],
    "UG": ["PSP_AIRTEL_UG"],
}

SMOVE_CURRENCIES = ["USD", "EUR", "GBP", "NGN", "ZAR", "EGP"]

LOCAL_CURRENCY = {
    "KE": "KES",
    "TZ": "TZS",
    "UG": "UGX",
}


def _load_store() -> Dict:
    if not STORE_PATH.exists():
        return {}

    with STORE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(data: Dict):
    with STORE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _new_balance(currency: str, amount: Optional[int] = None):
    return {
        "currency": currency,
        "available": amount if amount is not None else random.randint(100_000, 5_000_000),
        "reserved": 0,
    }


def generate_accounts(nid: str, country: str):
    with STORE_LOCK:
        data = _load_store()

        if nid in data:
            return data[nid]

        accounts = {}
        currency = LOCAL_CURRENCY[country]

        bank = BANKS.get(country)
        if bank:
            accounts[bank] = {}
            for _ in range(2):
                acc_id = f"{bank}-ACC-{country}-{random.randint(1000,9999)}"
                accounts[bank][acc_id] = _new_balance(currency)

        for wallet in PSP_WALLETS.get(country, []):
            accounts[wallet] = {}
            wallet_id = f"{wallet}-WALLET-{random.randint(1000,9999)}"
            accounts[wallet][wallet_id] = _new_balance(currency)

        accounts["SMOVE_WALLET"] = {}
        for fx in SMOVE_CURRENCIES:
            wallet_id = f"SMOVE-{fx}-{random.randint(1000,9999)}"
            accounts["SMOVE_WALLET"][wallet_id] = _new_balance(fx, 10_000)

        data[nid] = accounts
        _save_store(data)
        return accounts


def get_accounts(nid: str):
    with STORE_LOCK:
        return _load_store().get(nid, {})


def find_account(account_id: str) -> Tuple[Optional[str], Optional[str], Optional[dict], Dict]:
    data = _load_store()

    for nid, providers in data.items():
        for provider, accounts in providers.items():
            if account_id in accounts:
                return nid, provider, accounts[account_id], data

    return None, None, None, data


def lock_funds(account_id: str, amount: float) -> bool:
    with STORE_LOCK:
        nid, provider, account, data = find_account(account_id)
        if not account:
            return False

        if account["available"] < amount:
            return False

        account["available"] -= amount
        account["reserved"] += amount
        _save_store(data)
        return True


def release_funds(account_id: str, amount: float) -> bool:
    with STORE_LOCK:
        nid, provider, account, data = find_account(account_id)
        if not account:
            return False

        if account["reserved"] < amount:
            return False

        account["reserved"] -= amount
        account["available"] += amount
        _save_store(data)
        return True


def settle_locked_funds(account_id: str, amount: float) -> bool:
    with STORE_LOCK:
        nid, provider, account, data = find_account(account_id)
        if not account:
            return False

        if account["reserved"] < amount:
            return False

        account["reserved"] -= amount
        _save_store(data)
        return True


def credit_account(account_id: str, amount: float) -> bool:
    with STORE_LOCK:
        nid, provider, account, data = find_account(account_id)
        if not account:
            return False

        account["available"] += amount
        _save_store(data)
        return True


def get_balance(account_id: str):
    _, _, account, _ = find_account(account_id)
    return account