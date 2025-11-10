import sqlite3
import os
from openpyxl import Workbook
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "payments.db"


def export_to_excel(apartment_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
                SELECT c.utility_type,
                       c.period_start,
                       c.period_end,
                       c.amount,
                       IFNULL(SUM(p.amount), 0) as paid
                FROM charge c
                         LEFT JOIN payment p ON c.id = p.charge_id
                WHERE c.apartment_id = ?
                GROUP BY c.id
                ORDER BY c.period_end
                """, (apartment_id,))
    charges = cur.fetchall()
    conn.close()

    if not charges:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Начисления"
    ws.append(["Ресурс", "Период", "Начислено", "Оплачено", "Остаток"])

    util_ru = {"electricity": "Электричество", "water_hot": "ГВС", "water_cold": "ХВС", "gas": "Газ"}
    for ch in charges:
        debt = ch["amount"] - ch["paid"]
        period = f"{ch['period_start']} – {ch['period_end']}"
        ws.append([
            util_ru.get(ch["utility_type"], ch["utility_type"]),
            period,
            ch["amount"],
            ch["paid"],
            debt
        ])

    filename = f"/tmp/export_{apartment_id}.xlsx"
    wb.save(filename)
    return filename
