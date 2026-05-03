# ==============================
# network_seed.py (FULL NETWORK)
# ==============================
from account_seed import seed_user_accounts


from uuid import uuid4
from ledger.db import SessionLocal
from ledger.models import Institution, InstitutionKey, UserAccountLink, User
from user_directory import create_user

from ledger.db import engine
from ledger.models import Base
from core_registry import register_core

Base.metadata.create_all(bind=engine)


# --------------------------------
# INSTITUTIONS
# --------------------------------
def seed_institutions():

    session = SessionLocal()

    try:
        institutions = [

            # 🔥 CORE SYSTEM (CRITICAL)
            ("R1CORE", "RailOne Core", "CORE", "GLOBAL"),
            ("PSP_KE", "Kenya Mobile Money", "PSP", "KE"),
            ("BANK_TZ", "Tanzania Bank", "BANK", "TZ"),
            ("PSP_UG", "Uganda Wallet", "WALLET", "UG"),
        ]

        for inst_id, name, inst_type, country in institutions:

            exists = session.query(Institution).filter_by(id=inst_id).first()
            if exists:
                continue

            session.add(Institution(
                id=inst_id,
                name=name,
                type=inst_type,
                country=country,
                status="ACTIVE"
            ))

        session.commit()

    finally:
        session.close()


# --------------------------------
# KEYS
# --------------------------------
def seed_institution_keys():

    session = SessionLocal()

    try:
        institutions = session.query(Institution).all()

        for inst in institutions:

            exists = session.query(InstitutionKey).filter_by(
                institution_id=inst.id,
                status="ACTIVE"
            ).first()

            if exists:
                continue

            session.add(InstitutionKey(
                id=str(uuid4()),
                institution_id=inst.id,
                public_key=f"pubkey_{inst.id}",
                key_version="v1",
                status="ACTIVE"
            ))

        session.commit()

    finally:
        session.close()


# --------------------------------
# LINK USER TO INSTITUTIONS
# --------------------------------
def seed_user_links(railone_id):

    session = SessionLocal()

    try:
        links = [
            ("PSP_KE", f"{railone_id}_KE_MPESA", "KES"),
            ("BANK_TZ", f"{railone_id}_TZ_BANK", "TZS"),
            ("PSP_UG", f"{railone_id}_UG_WALLET", "UGX"),
        ]

        for inst_id, account_ref, currency in links:

            exists = session.query(UserAccountLink).filter_by(
                railone_id=railone_id,
                institution_id=inst_id,
                currency=currency
            ).first()

            if exists:
                continue

            session.add(UserAccountLink(
                id=str(uuid4()),
                railone_id=railone_id,
                institution_id=inst_id,
                external_account_ref=account_ref,
                currency=currency
            ))

        session.commit()

    finally:
        session.close()


# --------------------------------
# 🔥 MULTI-USER NETWORK
# --------------------------------
def seed_users():

    # 🔥 MUST MATCH identity_db.py
    users = [
        ("Faith Wanjiku", "10000891"),
        ("Juma Nyerere", "10000555"),
        ("Daniel Okello", "10000777"),
    ]

    created = []

    for name, nid in users:
        user = create_user(name, nid)
        railone_id = user["railone_id"]

        seed_user_links(railone_id)
        seed_user_accounts(railone_id)

        created.append({
            "name": name,
            "nid": nid,
            "railone_id": railone_id
        })

    return created

# --------------------------------
# LOOKUP USER BY NATIONAL ID
# --------------------------------
def get_railone_id_by_national_id(national_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(
            national_id=national_id
        ).first()

        if not user:
            return None

        return user.railone_id

    finally:
        session.close()


# --------------------------------
# ENTRY POINT
# --------------------------------
def seed_all():

    print("🌐 Seeding full RailOne network...")

    register_core()

    seed_institutions()
    seed_institution_keys()

    users = seed_users()

    print("\n👥 Users Created:")
    for u in users:
        print(f"- {u['name']} | {u['railone_id']}")

    print("\n✅ Network ready.")


if __name__ == "__main__":
    seed_all()