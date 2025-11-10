from .database import get_db


#
# import sqlite3
# from pathlib import Path

# DB_PATH = Path(__file__).parent.parent / "payments.db"

# def get_db():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     return conn

def get_apartment(apartment_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    return cur.fetchone()


def get_tariffs(apartment_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tariff WHERE apartment_id = ? ORDER BY utility_type, valid_from DESC", (apartment_id,))
    return cur.fetchall()


def upsert_tariff(apartment_id, utility_type, rate, valid_from):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
                INSERT INTO tariff (apartment_id, utility_type, rate, valid_from)
                VALUES (?, ?, ?, ?) ON CONFLICT(apartment_id, utility_type, valid_from) 
        DO
                UPDATE SET rate=excluded.rate
                """, (apartment_id, utility_type, rate, valid_from))
    conn.commit()


def get_residents(apartment_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
                SELECT r.id, r.telegram_id, r.full_name, res.is_admin
                FROM resident r
                         JOIN residency res ON r.id = res.resident_id
                WHERE res.apartment_id = ?
                """, (apartment_id,))
    return cur.fetchall()


def add_resident(apartment_id, telegram_id, full_name, is_admin):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO resident (telegram_id, full_name) VALUES (?, ?)", (telegram_id, full_name))
    resident_id = cur.lastrowid
    cur.execute("INSERT INTO residency (resident_id, apartment_id, is_admin) VALUES (?, ?, ?)",
                (resident_id, apartment_id, is_admin))
    conn.commit()


def is_admin_db(telegram_id, apartment_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
                SELECT 1
                FROM residency
                WHERE resident_id = (SELECT id FROM resident WHERE telegram_id = ?)
                  AND apartment_id = ?
                  AND is_admin = 1
                """, (telegram_id, apartment_id))
    return cur.fetchone() is not None
