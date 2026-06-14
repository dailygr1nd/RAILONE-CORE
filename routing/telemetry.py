# telemetry.py
from copy import deepcopy

# ==========================================
# LIVE TELEMETRY PER RAIL
# ==========================================
ROUTE_TELEMETRY = {
    "BANK_KE": {
        "success_rate": 0.996,
        "avg_latency_ms": 1300,
        "reversal_rate": 0.0015,
        "capacity_score": 0.98,
        "fx_strength": 0.95,
        "uptime": 0.999
    },

    "BANK_TZ": {
        "success_rate": 0.994,
        "avg_latency_ms": 1450,
        "reversal_rate": 0.0020,
        "capacity_score": 0.97,
        "fx_strength": 0.94,
        "uptime": 0.998
    },

    "BANK_UG": {
        "success_rate": 0.992,
        "avg_latency_ms": 1600,
        "reversal_rate": 0.0030,
        "capacity_score": 0.95,
        "fx_strength": 0.93,
        "uptime": 0.997
    },

    "PSP_KE": {
        "success_rate": 0.985,
        "avg_latency_ms": 650,
        "reversal_rate": 0.008,
        "capacity_score": 0.99,
        "fx_strength": 0.90,
        "uptime": 0.998
    },

    "PSP_TZ": {
        "success_rate": 0.982,
        "avg_latency_ms": 700,
        "reversal_rate": 0.010,
        "capacity_score": 0.98,
        "fx_strength": 0.89,
        "uptime": 0.997
    },

    "PSP_UG": {
        "success_rate": 0.980,
        "avg_latency_ms": 720,
        "reversal_rate": 0.011,
        "capacity_score": 0.97,
        "fx_strength": 0.88,
        "uptime": 0.996
    },

    "SMOVE": {
        "success_rate": 0.975,
        "avg_latency_ms": 520,
        "reversal_rate": 0.006,
        "capacity_score": 0.96,
        "fx_strength": 0.99,
        "uptime": 0.995
    }
}


# ==========================================
# FETCH TELEMETRY
# ==========================================
def get_telemetry(route_type):
    return deepcopy(
        ROUTE_TELEMETRY.get(route_type)
    )


# ==========================================
# UPDATE TELEMETRY AFTER TX
# ==========================================
def update_telemetry(route_type, success, latency_ms):
    if route_type not in ROUTE_TELEMETRY:
        return

    route = ROUTE_TELEMETRY[route_type]

    # rolling latency average
    route["avg_latency_ms"] = (
        route["avg_latency_ms"] * 0.8
        + latency_ms * 0.2
    )

    # success score drift
    if success:
        route["success_rate"] = min(
            0.999,
            route["success_rate"] + 0.0002
        )
    else:
        route["success_rate"] = max(
            0.90,
            route["success_rate"] - 0.003
        )