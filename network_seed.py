# ==============================
# network_seed.py
# ==============================

from uuid import uuid4
from ledger.db import SessionLocal
from ledger.models import Institution, InstitutionKey, UserAccountLink


def seed_institutions():

    session = SessionLocal()

    try:
        institutions = [
            ("PSP_KE", "Kenya Mobile Money", "PSP", "KE"),
            ("BANK_TZ", "Tanzania Bank", "BANK", "TZ"),
            ("PSP_UG", "Uganda Wallet", "WALLET", "UG"),
        ]

        for inst_id, name, inst_type, country in institutions:

            exists = session.query(Institution).filter_by(id=inst_id).first()
            if exists:
                continue

            inst = Institution(
                id=inst_id,
                name=name,
                type=inst_type,
                country=country,
                status="ACTIVE"
            )

            session.add(inst)

        session.commit()

    finally:
        session.close()


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

            key = InstitutionKey(
                id=str(uuid4()),
                institution_id=inst.id,
                public_key=f"pubkey_{inst.id}",  # 🔐 placeholder
                key_version="v1",
                status="ACTIVE"
            )

            session.add(key)

        session.commit()

    finally:
        session.close()


def seed_user_links(railone_id):

    session = SessionLocal()

    try:
        links = [
            ("PSP_KE", f"{railone_id}_254700000001", "KES"),
            ("BANK_TZ", f"{railone_id}_TZ_ACC_001", "TZS"),
            ("PSP_UG", f"{railone_id}_UG_WALLET_001", "UGX"),
        ]

        for inst_id, account_ref, currency in links:

            exists = session.query(UserAccountLink).filter_by(
                railone_id=railone_id,
                institution_id=inst_id,
                currency=currency
            ).first()

            if exists:
                continue

            link = UserAccountLink(
                id=str(uuid4()),
                railone_id=railone_id,
                institution_id=inst_id,
                external_account_ref=account_ref,
                currency=currency
            )

            session.add(link)

        session.commit()

    finally:
        session.close()


def seed_all(railone_id):
    seed_institutions()
    seed_institution_keys()
    seed_user_links(railone_id)