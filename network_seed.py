# ==========================================
# network_seed.py
# RailOne Execution Continuity Seed
# ==========================================

from uuid import uuid4

from ledger.db import (
    SessionLocal,
    engine
)

from ledger.models import (
    Institution,
    UserAccountLink
)

from ledger.account_service import (
    ensure_execution_account_exists
)

from institutions.auth_registry import (
    INSTITUTION_REGISTRY
)

from crypto.key_manager import (
    KeyManager
)

from identity.user_service import (
    onboard_user
)

from identity.account_seed import (
    seed_user_accounts
)

from identity.models import User

from db import Base

from institutions.core_registry import (
    register_core
)


# ==========================================
# CREATE TABLES
# ==========================================
Base.metadata.create_all(
    bind=engine
)


# ==========================================
# SEED INSTITUTIONS
# ==========================================
def seed_institutions():

    session = SessionLocal()

    try:

        for (
            institution_id,
            config
        ) in INSTITUTION_REGISTRY.items():

            exists = (

                session.query(Institution)

                .filter_by(
                    institution_id=institution_id
                )

                .first()
            )

            if exists:
                continue

            institution = Institution(

                institution_id=(
                    institution_id
                ),

                institution_name=(
                    institution_id
                ),

                institution_type=(
                    config.get(
                        "institution_type"
                    )
                ),

                country=(
                    config.get(
                        "country"
                    )
                ),

                operational_status=(
                    "ACTIVE"
                ),

                supported_adapters=(
                    config.get(
                        "supported_adapters",
                        []
                    )
                ),

                supported_currencies=(
                    config.get(
                        "supported_currencies",
                        []
                    )
                ),

                replay_policy=(
                    config.get(
                        "replay_policy",
                        {}
                    )
                ),

                execution_policy=(
                    config.get(
                        "execution_policy",
                        {}
                    )
                ),

                attestation_capable=(
                    config.get(
                        "attestation_capable",
                        False
                    )
                )
            )

            session.add(
                institution
            )

        session.commit()

        print(
            "✅ Institutions seeded"
        )

    finally:

        session.close()


# ==========================================
# CRYPTOGRAPHIC TRUST LAYER
# ==========================================
def seed_cryptographic_layer():

    print(
        "\n🔐 Initializing "
        "execution trust layer..."
    )

    for institution_id in (
        INSTITUTION_REGISTRY.keys()
    ):

        KeyManager.ensure_institution_keys(
            institution_id
        )

    print(
        "✅ Cryptographic layer ready"
    )


# ==========================================
# USER ACCOUNT LINKS
# ==========================================
def seed_user_links(

    railone_id,

    continuity_uid
):

    session = SessionLocal()

    try:

        links = [

            (
                "MPESA",
                f"{railone_id}_MPESA",
                "KES",
                "mpesa"
            ),

            (
                "BANK_KE",
                f"{railone_id}_BANK_KE",
                "KES",
                "flutterwave"
            )
        ]

        for (

            institution_id,

            external_ref,

            currency,

            adapter_type

        ) in links:

            exists = (

                session.query(
                    UserAccountLink
                )

                .filter_by(

                    railone_id=(
                        railone_id
                    ),

                    institution_id=(
                        institution_id
                    ),

                    currency=currency
                )

                .first()
            )

            if exists:
                continue

            link = UserAccountLink(

                id=str(uuid4()),

                railone_id=(
                    railone_id
                ),

                continuity_uid=(
                    continuity_uid
                ),

                institution_id=(
                    institution_id
                ),

                adapter_type=(
                    adapter_type
                ),

                external_account_ref=(
                    external_ref
                ),

                currency=currency,

                linkage_state="ACTIVE"
            )

            session.add(link)

        session.commit()

        print(
            f"🔗 Linked execution "
            f"surfaces for "
            f"{railone_id}"
        )

    finally:

        session.close()


# ==========================================
# EXECUTION SURFACES
# ==========================================
def seed_execution_surfaces(

    railone_id,

    continuity_uid
):

    ensure_execution_account_exists(

        account_id=(
            f"{railone_id}_KES_MPESA"
        ),

        railone_id=railone_id,

        continuity_uid=(
            continuity_uid
        ),

        institution_id="MPESA",

        adapter_type="mpesa",

        currency="KES",

        mirrored_available_state=(
            250000.0
        )
    )

    ensure_execution_account_exists(

        account_id=(
            f"{railone_id}_BANK_KE"
        ),

        railone_id=railone_id,

        continuity_uid=(
            continuity_uid
        ),

        institution_id="BANK_KE",

        adapter_type="flutterwave",

        currency="KES",

        mirrored_available_state=(
            500000.0
        )
    )

    print(
        f"💧 Execution surfaces "
        f"seeded for "
        f"{railone_id}"
    )


# ==========================================
# SEED USERS
# ==========================================
def seed_users():

    users = [

        {
            "name":
                "Faith Wanjiku",

            "national_id":
                "10000891",

            "corridor":
                "KE"
        },

        {
            "name":
                "Juma Nyerere",

            "national_id":
                "10000555",

            "corridor":
                "TZ"
        },

        {
            "name":
                "Daniel Okello",

            "national_id":
                "10000777",

            "corridor":
                "UG"
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

            national_id=(
                entry["national_id"]
            ),

            corridor=(
                entry["corridor"]
            )
        )

        railone_id = (
            user["railone_id"]
        )

        continuity_uid = (
            user["continuity_uid"]
        )

        # ==============================
        # LINKAGES
        # ==============================
        seed_user_links(

            railone_id,

            continuity_uid
        )

        # ==============================
        # EXECUTION SURFACES
        # ==============================
        seed_execution_surfaces(

            railone_id,

            continuity_uid
        )

        # ==============================
        # IDENTITY ACCOUNTS
        # ==============================
        seed_user_accounts(

            railone_id,

            continuity_uid
        )

        created.append({

            "name":
                entry["name"],

            "railone_id":
                railone_id,

            "continuity_uid":
                continuity_uid,

            "corridor":
                entry["corridor"]
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
        "\n🌐 Initializing "
        "RailOne Execution Network..."
    )

    # ======================================
    # CORE TRUST DOMAIN
    # ======================================
    register_core()

    # ======================================
    # INSTITUTIONS
    # ======================================
    seed_institutions()

    # ======================================
    # CRYPTOGRAPHIC TRUST
    # ======================================
    seed_cryptographic_layer()

    # ======================================
    # USERS
    # ======================================
    users = seed_users()

    print("\n👥 USERS CREATED:")

    for u in users:

        print(
            "\n================================"
        )

        print(
            f"👤 {u['name']}"
        )

        print(
            f"🆔 RailOne ID: "
            f"{u['railone_id']}"
        )

        print(
            f"🔗 Continuity UID: "
            f"{u['continuity_uid']}"
        )

        print(
            f"🌍 Corridor: "
            f"{u['corridor']}"
        )

    print(
        "\n✅ RailOne network "
        "seed complete"
    )


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":

    seed_all()