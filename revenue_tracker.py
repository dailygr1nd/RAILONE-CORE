# ==============================
# revenue_tracker.py
# ==============================

TOTAL_REVENUE = 0


def record_revenue(amount):
    global TOTAL_REVENUE
    TOTAL_REVENUE += amount


def get_revenue():
    return TOTAL_REVENUE