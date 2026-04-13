ROUTE_TELEMETRY = {
    "PSP": {
        "success_rate": 0.98,
        "avg_latency_ms": 620,
        "reversal_rate": 0.01,
    },
    "BANK": {
        "success_rate": 0.995,
        "avg_latency_ms": 1400,
        "reversal_rate": 0.002,
    },
    "WALLET": {
        "success_rate": 0.96,
        "avg_latency_ms": 480,
        "reversal_rate": 0.015,
    },
}


def get_telemetry(route_type):
    return ROUTE_TELEMETRY.get(route_type)
