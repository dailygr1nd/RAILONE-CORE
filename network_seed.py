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

    (
        "MPESA",
        "Safaricom M-PESA",
        "MOBILE_MONEY",
        "KE"
    ),

    (
        "BANK_KE",
        "Kenya Interbank Rail",
        "BANK",
        "KE"
    ),

    (
        "BANK_UG",
        "Uganda Settlement Rail",
        "BANK",
        "UG"
    ),

    (
        "BANK_TZ",
        "Tanzania Settlement Rail",
        "BANK",
        "TZ"
    ),

    (
        "SMOVE",
        "SMOVE Wallet",
        "WALLET",
        "EA"
    ),

    (
        "R1CORE",
        "RailOne Core Network",
        "EXECUTION_CORE",
        "GLOBAL"
    )
]

        for inst_id, inst_name, inst_type, corridor in institutions:

            exists = (

                session.query(Institution)

                .filter_by(institution_id=inst_id)

                .first()
            )

            if exists:
                continue

            session.add(

                Institution(
                    institution_id=inst_id,
                    institution_name=inst_name,
                    institution_type=inst_type,
                    corridor=corridor,
                    operational_status="ACTIVE"
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

                    institution_id=inst.institution_id,

                    status="ACTIVE"
                )

                .first()
            )

            if exists:
                continue

            session.add(

                InstitutionKey(

                    id=str(uuid4()),

                    institution_id=inst.institution_id,

                    public_key=f"pubkey_{inst.institution_id}",

                    private_key=f"privkey_{inst.institution_id}",

                    key_type="RSA",

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
def seed_user_links( railone_id, continuity_uid):

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

                    continuity_uid=continuity_uid,

                    institution_id=inst_id,

                    external_account_ref=account_ref,

                    currency=currency,

                    linkage_state="ACTIVE"
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
            "national_id": "10000891",
            "corridor": "KE"
        },

        {
            "name": "Juma Nyerere",
            "national_id": "10000555",
            "corridor": "TZ"
        },

        {
            "name": "Daniel Okello",
            "national_id": "10000777",
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

            national_id=entry["national_id"],

            corridor=entry["corridor"]
        )

        railone_id = user["railone_id"]

        continuity_uid = user["continuity_uid"]

        seed_user_links( railone_id, continuity_uid)

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