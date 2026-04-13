# identity_db.py

IDENTITY_DB = {
    # TANZANIA
    "10000554": {"name": "Amani Mwangi", "country": "TZ", "dob": "1998-04-12", "status": "valid"},
    "10000555": {"name": "Juma Nyerere", "country": "TZ", "dob": "1990-02-01", "status": "valid"},
    "10000556": {"name": "Neema Hassan", "country": "TZ", "dob": "1995-07-19", "status": "valid"},

    # KENYA
    "10000889": {"name": "Zuri Okoye", "country": "KE", "dob": "1995-09-21", "status": "valid"},
    "10000890": {"name": "Brian Otieno", "country": "KE", "dob": "1993-03-11", "status": "valid"},
    "10000891": {"name": "Faith Wanjiku", "country": "KE", "dob": "1999-12-05", "status": "valid"},
    "10000997": {"name": "Faith Njoroge", "country": "KE", "dob": "1997-05-11", "status": "valid"},
    "19980000": {"name": "Tyrus Njugu", "country": "KE", "dob": "1996-04-02", "status": "valid"},

    # UGANDA
    "10000777": {"name": "Daniel Okello", "country": "UG", "dob": "1991-06-14", "status": "valid"},
    "10000778": {"name": "Grace Nakitende", "country": "UG", "dob": "1997-08-22", "status": "valid"},

    # US
    "10000999": {"name": "John Doe", "country": "US", "dob": "1985-05-10", "status": "valid"},
    "10001000": {"name": "Jane Smith", "country": "US", "dob": "1990-11-30", "status": "valid"},
}

# Sample accounts for simplicity
ACCOUNTS_DB = {
    "10000889": [  # Zuri Okoye
        {"type": "PSP", "name": "MPESA-KE-322", "balance": 1891105.0, "currency": "KES"},
        {"type": "PSP", "name": "AIRTEL-KE-318", "balance": 466463.0, "currency": "KES"},
        {"type": "LEGACY_INT", "name": "USD-298", "balance": 1966.0, "currency": "USD"},
        {"type": "WALLET", "name": "WLT-443", "balance": 690.0, "currency": "USD"},
        {"type": "BANK", "name": "BAN-BAN-KE-952", "balance": 2414602.0, "currency": "KES"},
        {"type": "BANK", "name": "BAN-BAN-KE-297", "balance": 1791431.0, "currency": "KES"},
    ],
    "10000555": [  # Juma Nyerere
        {"type": "PSP", "name": "MPESA-TZ-260", "balance": 3440068.0, "currency": "TZS"},
        {"type": "PSP", "name": "AIRTEL-TZ-125", "balance": 2097143.0, "currency": "TZS"},
        {"type": "LEGACY_INT", "name": "USD-533", "balance": 2755.0, "currency": "USD"},
        {"type": "WALLET", "name": "WLT-992", "balance": 375.0, "currency": "USD"},
        {"type": "BANK", "name": "BAN-BAN-TZ-165", "balance": 3659933.0, "currency": "TZS"},
        {"type": "BANK", "name": "BAN-BAN-TZ-212", "balance": 3035917.0, "currency": "TZS"},
    ],
    "10000997": [  # Faith Njoroge
        {"type": "PSP", "name": "MPESA-KE-208", "balance": 1468918.0, "currency": "KES"},
        {"type": "PSP", "name": "AIRTEL-KE-230", "balance": 4414725.0, "currency": "KES"},
        {"type": "LEGACY_INT", "name": "USD-918", "balance": 4546.0, "currency": "USD"},
        {"type": "WALLET", "name": "WLT-122", "balance": 260.0, "currency": "USD"},
        {"type": "BANK", "name": "BAN-BAN-KE-603", "balance": 850318.0, "currency": "KES"},
        {"type": "BANK", "name": "BAN-BAN-KE-522", "balance": 193159.0, "currency": "KES"},
    ],
    "19980000": [  # Tyrus Njugu
        {"type": "PSP", "name": "MPESA-KE-347", "balance": 3542777.0, "currency": "KES"},
        {"type": "PSP", "name": "AIRTEL-KE-864", "balance": 4824628.0, "currency": "KES"},
        {"type": "LEGACY_INT", "name": "USD-255", "balance": 1160.0, "currency": "USD"},
        {"type": "WALLET", "name": "WLT-313", "balance": 351.0, "currency": "USD"},
        {"type": "BANK", "name": "BAN-BAN-KE-272", "balance": 2597918.0, "currency": "KES"},
        {"type": "BANK", "name": "BAN-BAN-KE-799", "balance": 4406333.0, "currency": "KES"},
    ],
}

def lookup_identity(nid, name):
    record = IDENTITY_DB.get(nid)
    if record is None:
        return None
    if record["name"].lower() != name.lower():
        return "NAME_MISMATCH"
    # add accounts
    record_copy = record.copy()
    record_copy["accounts"] = ACCOUNTS_DB.get(nid, [])
    return record_copy