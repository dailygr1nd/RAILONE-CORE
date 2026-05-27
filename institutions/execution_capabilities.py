# ==========================================
# institutions/execution_capabilities.py
# RailOne Execution Capability Registry
# ==========================================

EXECUTION_CAPABILITIES = {

    # ======================================
    # MPESA
    # ======================================
    "MPESA": {

        "institution_type":
            "MOBILE_MONEY",

        "country":
            "KE",

        "supported_adapters": [
            "mpesa"
        ],

        "supported_currencies": [
            "KES"
        ],

        "execution_modes": [
            "MOBILE_MONEY"
        ],

        "execution_policy": {

            "settlement_model":
                "ASYNC",

            "webhook_required":
                True,

            "supports_replay":
                True,

            "supports_recovery":
                True,
        },

        "replay_policy": {

            "max_retries":
                3,

            "requires_reconciliation":
                True,

            "manual_review_threshold":
                100000,
        }
    },

    # ======================================
    # BANK_KE
    # ======================================
    "BANK_KE": {

        "institution_type":
            "BANK",

        "country":
            "KE",

        "supported_adapters": [
            "flutterwave",
            "paystack"
        ],

        "supported_currencies": [
            "KES",
            "USD"
        ],

        "execution_modes": [
            "BANK_TRANSFER"
        ],

        "execution_policy": {

            "settlement_model":
                "SYNC",

            "webhook_required":
                True,

            "supports_replay":
                True,

            "supports_recovery":
                True,
        },

        "replay_policy": {

            "max_retries":
                2,

            "requires_reconciliation":
                True,

            "manual_review_threshold":
                250000,
        }
    },

    # ======================================
    # R1CORE
    # ======================================
    "R1CORE": {

        "institution_type":
            "CORE_ORCHESTRATOR",

        "country":
            "MULTI",

        "supported_adapters": [
            "mpesa",
            "flutterwave",
            "paystack"
        ],

        "supported_currencies": [
            "KES",
            "USD",
            "UGX",
            "TZS"
        ],

        "execution_modes": [
            "ORCHESTRATION"
        ],

        "execution_policy": {

            "settlement_model":
                "NON_CUSTODIAL",

            "webhook_required":
                False,

            "supports_replay":
                True,

            "supports_recovery":
                True,
        },

        "replay_policy": {

            "max_retries":
                5,

            "requires_reconciliation":
                True,

            "manual_review_threshold":
                500000,
        }
    }
}