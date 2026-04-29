# ==============================
# revenue_db.py (UPGRADED)
# ==============================

import sqlite3

DB = "railone_revenue.db"


def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS revenue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_id TEXT,
        gross_amount REAL,
        fee_amount REAL,
        fx_profit REAL,
        total_revenue REAL,
        currency TEXT,
        route TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def record_revenue(
    tx_id,
    gross_amount,
    fee_amount,
    fx_profit,
    currency,
    route
):
    total_revenue = fee_amount + fx_profit

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO revenue (
        tx_id, gross_amount, fee_amount,
        fx_profit, total_revenue,
        currency, route
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        tx_id,
        gross_amount,
        fee_amount,
        fx_profit,
        total_revenue,
        currency,
        route
    ))

    conn.commit()
    conn.close()


def get_total_revenue():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT SUM(total_revenue) FROM revenue")
    result = c.fetchone()[0]

    conn.close()
    return result or 0


init()