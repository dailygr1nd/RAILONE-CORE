# ==============================
# seed_users.py
# ==============================

from user_service import onboard_user
from network_seed import seed_all


def seed_demo_users():

    demo_users = [
        ("faith wanjiku", "10000891"),
        ("john doe", "10000889"),
        ("alice kim", "10000555"),
    ]

    for name, nid in demo_users:
        rid = onboard_user(name, nid)
        seed_all(rid)

    print("✅ Demo users seeded")