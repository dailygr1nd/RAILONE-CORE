# ==============================
# beneficiary_db.py
# ==============================

import sqlite3

DB = "railone_users.db"


def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS beneficiaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        name TEXT,
        account_id TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_beneficiary(user_id, name, account_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO beneficiaries (user_id, name, account_id)
    VALUES (?, ?, ?)
    """, (user_id, name, account_id))

    conn.commit()
    conn.close()


def get_beneficiaries(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    SELECT id, name, account_id
    FROM beneficiaries
    WHERE user_id = ?
    """, (user_id,))

    rows = c.fetchall()
    conn.close()

    return rows


init()