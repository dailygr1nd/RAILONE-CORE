from psp_ke import PSPKenya
from bank_tz import BankTanzania
from psp_ug import WalletUganda
from institution_router import InstitutionRouter

# Instantiate institutions
psp_ke = PSPKenya("PSP_KE", "key_ke")
bank_tz = BankTanzania("BANK_TZ", "key_tz")
wallet_ug = WalletUganda("WALLET_UG", "key_ug")

# Seed balances
psp_ke.ledger["user_ke"] = 20000
bank_tz.ledger["user_tz"] = 5000
wallet_ug.ledger["user_ug"] = 3000

# Registry
router = InstitutionRouter({
    "PSP_KE": psp_ke,
    "BANK_TZ": bank_tz,
    "WALLET_UG": wallet_ug
})