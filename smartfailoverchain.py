from railhealth import update_health
from processingdispatcher import process_route
def smart_failover(initial_route, amount, append_log):

    failover_chain = [
        initial_route,
        {"name": "LEGACY_BANK", "type": "BANK_FAIL"},
        {"name": "BANK_A", "type": "BANK_A"},
        {"name": "BANK_B", "type": "BANK_B"},
        {"name": "MOBILE_MONEY", "type": "PSP"},
    ]

    tried = set()

    for route in failover_chain:

        if route["type"] in tried:
            continue

        tried.add(route["type"])

        print(f"\n🔁 Trying route: {route['name']}")

        result = process_route(route, amount)

        update_health(route["type"], result["Status"])

        append_log("ROUTE_ATTEMPT", {
            "route": route["name"],
            "status": result["Status"]
        })

        if result["Status"] == "Executed":
            return result

        append_log("ROUTE_FAILED", {
            "route": route["name"],
            "reason": result.get("Reason")
        })

    return {
        "Status": "Failed",
        "Reason": "ALL_ROUTES_FAILED"
    }