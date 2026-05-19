# ==============================
# network_seed.py
# RailOne Identity Moat Network Seed
# ==============================

from uuid import uuid4

from identity.account_seed import (
    seed_user_accounts
)

from identity.user_service import (
    onboard_user
)

from ledger.db import (
    SessionLocal,
    engine
)

from ledger.models import (

    Institution,
    InstitutionKey,
    UserAccountLink
)

from identity.models import User

from db import Base

from core_registry import register_core


# ==========================================
# CREATE TABLES
# ==========================================
Base.metadata.create_all(bind=engine)


# ==========================================
# INSTITUTIONS
# ==========================================
def seed_institutions():

    session = SessionLocal()

    try:

        institutions = [

            # --------------------------------
            # CORE RAILONE
            # --------------------------------
            (
                "R1CORE",
                "RailOne Core",
                "CORE",
                "GLOBAL"
            ),

            # --------------------------------
            # EAST AFRICA CORRIDOR
            # --------------------------------
            (
                "PSP_KE",
                "Kenya Mobile Money",
                "PSP",
                "KE"
            ),

            (
                "BANK_TZ",
                "Tanzania Bank",
                "BANK",
                "TZ"
            ),

            (
                "PSP_UG",
                "Uganda Wallet",
                "WALLET",
                "UG"
            ),
        ]

        for inst_id, name, inst_type, country in institutions:

            exists = (

                session.query(Institution)

                .filter_by(id=inst_id)

                .first()
            )

            if exists:
                continue

            session.add(

                Institution(

                    id=inst_id,

                    name=name,

                    type=inst_type,

                    country=country,

                    status="ACTIVE"
                )
            )

        session.commit()

        print("✅ Institutions seeded")

    finally:

        session.close()


# ==========================================
# INSTITUTION KEYS
# ==========================================
def seed_institution_keys():

    session = SessionLocal()

    try:

        institutions = (

            session.query(Institution)

            .all()
        )

        for inst in institutions:

            exists = (

                session.query(InstitutionKey)

                .filter_by(

                    institution_id=inst.id,

                    status="ACTIVE"
                )

                .first()
            )

            if exists:
                continue

            session.add(

                InstitutionKey(

                    id=str(uuid4()),

                    institution_id=inst.id,

                    public_key=f"pubkey_{inst.id}",

                    key_version="v1",

                    status="ACTIVE"
                )
            )

        session.commit()

        print("✅ Institution keys seeded")

    finally:

        session.close()


# ==========================================
# LINK USER TO INSTITUTIONS
# ==========================================
def seed_user_links(railone_id):

    session = SessionLocal()

    try:

        links = [

            (
                "PSP_KE",
                f"{railone_id}_KE_MPESA",
                "KES"
            ),

            (
                "BANK_TZ",
                f"{railone_id}_TZ_BANK",
                "TZS"
            ),

            (
                "PSP_UG",
                f"{railone_id}_UG_WALLET",
                "UGX"
            ),
        ]

        for inst_id, account_ref, currency in links:

            exists = (

                session.query(UserAccountLink)

                .filter_by(

                    railone_id=railone_id,

                    institution_id=inst_id,

                    currency=currency
                )

                .first()
            )

            if exists:
                continue

            session.add(

                UserAccountLink(

                    id=str(uuid4()),

                    railone_id=railone_id,

                    institution_id=inst_id,

                    external_account_ref=account_ref,

                    currency=currency
                )
            )

        session.commit()

    finally:

        session.close()


# ==========================================
# EAST AFRICA CORRIDOR USERS
# ==========================================
def seed_users():

    users = [

        {
            "name": "Faith Wanjiku",
            "nid": "10000891",
            "corridor": "KE"
        },

        {
            "name": "Juma Nyerere",
            "nid": "10000555",
            "corridor": "TZ"
        },

        {
            "name": "Daniel Okello",
            "nid": "10000777",
            "corridor": "UG"
        }
    ]

    created = []

    for entry in users:

        print(
            f"\n👤 Onboarding "
            f"{entry['name']} "
            f"({entry['corridor']})"
        )

        user = onboard_user(

            name=entry["name"],

            nid=entry["nid"],

            corridor=entry["corridor"]
        )

        railone_id = user["railone_id"]

        continuity_uid = user["continuity_uid"]

        seed_user_links(railone_id)

        seed_user_accounts(

            railone_id,

            continuity_uid
        )

        created.append({

            "name": entry["name"],

            "railone_id": railone_id,

            "continuity_uid": continuity_uid,

            "corridor": entry["corridor"]
        })

    return created


# ==========================================
# LOOKUP USER
# ==========================================
def get_railone_id_by_national_id(
    national_id
):

    session = SessionLocal()

    try:

        user = (

            session.query(User)

            .filter_by(
                national_id=national_id
            )

            .first()
        )

        if not user:
            return None

        return user.railone_id

    finally:

        session.close()


# ==========================================
# FULL NETWORK SEED
# ==========================================
def seed_all():

    print(
        "\\n🌐 Initializing RailOne "
        "Identity Moat Network..."
    )

    # --------------------------------
    # CORE REGISTRY
    # --------------------------------
    register_core()

    # --------------------------------
    # INSTITUTIONS
    # --------------------------------
    seed_institutions()

    # --------------------------------
    # KEYS
    # --------------------------------
    seed_institution_keys()

    # --------------------------------
    # USERS
    # --------------------------------
    users = seed_users()

    print("\\n👥 USERS CREATED:")

    for u in users:

        print("\n================================")

        print(f"👤 {u['name']}")

        print(f"🆔 RailOne ID: {u['railone_id']}")

        print(
            f"🔗 Continuity UID: "
            f"{u['continuity_uid']}"
    )

    print(f"🌍 Corridor: {u['corridor']}")


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":

    seed_all()