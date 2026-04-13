# railhealth.py

rail_health = {
     "BANK_FAIL": {"success": 0, "fail": 0}, 
    "BANK_A": {"success": 0, "fail": 0},
    "BANK_B": {"success": 0, "fail": 0},
    "PSP": {"success": 0, "fail": 0},
    "BANK_FAIL": {"success": 0, "fail": 0},
}

def update_health(route_type, status):
    if status == "Executed":
        rail_health[route_type]["success"] += 1
    else:
        rail_health[route_type]["fail"] += 1


def get_success_rate(route_type):
    data = rail_health.get(route_type, {"success": 0, "fail": 0})
    total = data["success"] + data["fail"]

    if total == 0:
        return 1  # assume perfect initially

    return data["success"] / total


def print_health():
    print("\n📊 Rail Health Status:")
    for rail, data in rail_health.items():
        rate = get_success_rate(rail)
        print(f"{rail}: {rate:.2f} success rate")