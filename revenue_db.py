# ==============================
# revenue_db.py
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
        amount REAL,
        currency TEXT,
        route TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def record_revenue(tx_id, amount, currency, route):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO revenue (tx_id, amount, currency, route)
    VALUES (?, ?, ?, ?)
    """, (tx_id, amount, currency, route))

    conn.commit()
    conn.close()


def get_total_revenue():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM revenue")
    result = c.fetchone()[0]

    conn.close()

    return result or 0


def get_revenue_breakdown():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    SELECT route, SUM(amount)
    FROM revenue
    GROUP BY route
    """)

    rows = c.fetchall()
    conn.close()

    return rows


# initialize on import
init()