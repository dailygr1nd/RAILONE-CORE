# rail_executor.py

import random
import time


# --------------------------------
# SIMULATED BANK RAIL
# --------------------------------
def simulate_bank(tx):
    time.sleep(0.3)

    success = random.random() > 0.02  # 98% success

    if not success:
        return {
            "success": False,
            "reason": "BANK_TIMEOUT"
        }

    return {
        "success": True,
        "rail": "BANK",
        "reference": f"BANK-{int(time.time() * 1000)}"
    }


# --------------------------------
# SIMULATED PSP RAIL
# --------------------------------
def simulate_psp(tx):
    time.sleep(0.2)

    success = random.random() > 0.05  # 95% success

    if not success:
        return {
            "success": False,
            "reason": "PSP_FAILURE"
        }

    return {
        "success": True,
        "rail": "PSP",
        "reference": f"PSP-{int(time.time() * 1000)}"
    }


# --------------------------------
# SMOVE (INTERNAL LIQUIDITY RAIL)
# --------------------------------
def simulate_smove(tx):
    time.sleep(0.1)

    return {
        "success": True,
        "rail": "SMOVE",
        "reference": f"SMV-{int(time.time() * 1000)}"
    }


# --------------------------------
# MAIN EXECUTION ROUTER
# --------------------------------
def execute_on_rail(route, tx):
    rail = route.get("rail", "SMOVE")

    if "BANK" in rail:
        return simulate_bank(tx)

    if "PSP" in rail:
        return simulate_psp(tx)

    if "SMOVE" in rail:
        return simulate_smove(tx)

    return {
        "success": False,
        "reason": "UNKNOWN_RAIL"
    }