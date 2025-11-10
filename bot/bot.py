import asyncio
import logging
import os
from datetime import date
from uuid import uuid4

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from decouple import config
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# import sqlite3
from database import get_db_connection

# === CONFIG ===
BOT_TOKEN = config('BOT_TOKEN')
MEDIA_ROOT = "media/receipts"
os.makedirs(MEDIA_ROOT, exist_ok=True)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"


# DB_PATH = "payments.db"


# === DATABASE ===
def init_db():
    # conn = sqlite3.connect(DB_PATH)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS apartment
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    name
                    TEXT
                    NOT
                    NULL
                )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS resident
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    telegram_id
                    INTEGER
                    UNIQUE
                    NOT
                    NULL,
                    full_name
                    TEXT
                    NOT
                    NULL
                )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS residency
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    resident_id
                    INTEGER
                    NOT
                    NULL,
                    apartment_id
                    INTEGER
                    NOT
                    NULL,
                    is_admin
                    BOOLEAN
                    DEFAULT
                    0,
                    FOREIGN
                    KEY
                (
                    resident_id
                ) REFERENCES resident
                (
                    id
                ),
                    FOREIGN KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                ),
                    UNIQUE
                (
                    resident_id,
                    apartment_id
                )
                    )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS tariff
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    apartment_id
                    INTEGER
                    NOT
                    NULL,
                    utility_type
                    TEXT
                    NOT
                    NULL,
                    rate
                    REAL
                    NOT
                    NULL,
                    valid_from
                    TEXT
                    NOT
                    NULL,
                    FOREIGN
                    KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                ),
                    UNIQUE
                (
                    apartment_id,
                    utility_type,
                    valid_from
                )
                    )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS meter_reading
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    apartment_id
                    INTEGER
                    NOT
                    NULL,
                    utility_type
                    TEXT
                    NOT
                    NULL,
                    reading
                    REAL
                    NOT
                    NULL,
                    reading_date
                    TEXT
                    NOT
                    NULL,
                    submitted_by
                    INTEGER
                    NOT
                    NULL,
                    FOREIGN
                    KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                ),
                    FOREIGN KEY
                (
                    submitted_by
                ) REFERENCES resident
                (
                    id
                ),
                    UNIQUE
                (
                    apartment_id,
                    utility_type,
                    reading_date
                )
                    )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS charge
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    apartment_id
                    INTEGER
                    NOT
                    NULL,
                    utility_type
                    TEXT
                    NOT
                    NULL,
                    period_start
                    TEXT
                    NOT
                    NULL,
                    period_end
                    TEXT
                    NOT
                    NULL,
                    consumption
                    REAL
                    NOT
                    NULL,
                    tariff_used
                    REAL
                    NOT
                    NULL,
                    amount
                    REAL
                    NOT
                    NULL,
                    FOREIGN
                    KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                )
                    )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS payment
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    apartment_id
                    INTEGER
                    NOT
                    NULL,
                    charge_id
                    INTEGER,
                    amount
                    REAL
                    NOT
                    NULL,
                    date
                    TEXT
                    NOT
                    NULL,
                    created_at
                    TEXT
                    DEFAULT (
                    DATETIME
                (
                    'now'
                )),
                    confirmed_by INTEGER NOT NULL,
                    receipt_path TEXT,
                    FOREIGN KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                ),
                    FOREIGN KEY
                (
                    charge_id
                ) REFERENCES charge
                (
                    id
                ),
                    FOREIGN KEY
                (
                    confirmed_by
                ) REFERENCES resident
                (
                    id
                )
                    )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS apartment_region
                (
                    apartment_id
                    INTEGER
                    PRIMARY
                    KEY,
                    region_name
                    TEXT
                    NOT
                    NULL,
                    housing_type
                    TEXT
                    DEFAULT
                    'urban',
                    last_updated
                    TEXT,
                    FOREIGN
                    KEY
                (
                    apartment_id
                ) REFERENCES apartment
                (
                    id
                )
                    )
                """)
    conn.commit()
    conn.close()


async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)


# === HELPERS ===
# def get_db_connection():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     return conn

def get_or_create_resident(telegram_id: int, full_name: str = "Пользователь") -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM resident WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["id"]
    cur.execute("INSERT INTO resident (telegram_id, full_name) VALUES (?, ?)", (telegram_id, full_name))
    resident_id = cur.lastrowid
    conn.commit()
    conn.close()
    return resident_id


def get_resident_apartment(telegram_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                SELECT a.id, a.name
                FROM apartment a
                         JOIN residency r ON a.id = r.apartment_id
                         JOIN resident res ON r.resident_id = res.id
                WHERE res.telegram_id = ?
                """, (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def is_admin(telegram_id: int, apartment_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                SELECT 1
                FROM residency
                WHERE resident_id = (SELECT id FROM resident WHERE telegram_id = ?)
                  AND apartment_id = ?
                  AND is_admin = 1
                """, (telegram_id, apartment_id))
    result = cur.fetchone() is not None
    conn.close()
    return result


def get_unpaid_charges(apartment_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                SELECT c.id,
                       c.utility_type,
                       c.period_start,
                       c.period_end,
                       c.amount,
                       IFNULL(SUM(p.amount), 0) as paid
                FROM charge c
                         LEFT JOIN payment p ON c.id = p.charge_id
                WHERE c.apartment_id = ?
                GROUP BY c.id
                HAVING (c.amount - IFNULL(SUM(p.amount), 0)) > 0.01
                ORDER BY c.period_end ASC
                """, (apartment_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def save_payment_for_charge(charge_id: int, apartment_id: int, amount: float, resident_id: int,
                            receipt_path: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                INSERT INTO payment (apartment_id, charge_id, amount, date, confirmed_by, receipt_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (apartment_id, charge_id, amount, date.today().isoformat(), resident_id, receipt_path))
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id


UTILITIES_RU = {
    "electricity": "Электричество",
    "water_hot": "Горячая вода",
    "water_cold": "Холодная вода",
    "gas": "Газ"
}


# === FSM ===
class PayForChargeStates(StatesGroup):
    choosing_charge = State()
    entering_amount = State()
    confirming = State()


# === BOT ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    get_or_create_resident(message.from_user.id, message.from_user.full_name or "Пользователь")
    apt = get_resident_apartment(message.from_user.id)
    if apt:
        await message.answer(f"🏠 Добро пожаловать в {apt['name']}!\nКоманды: /pay, /my_apartment, /web_login")
    else:
        await message.answer("Вы не привязаны к квартире.")


@router.message(Command("my_apartment"))
async def cmd_my_apartment(message: Message):
    apartment = get_resident_apartment(message.from_user.id)
    if not apartment:
        await message.answer("Не привязан к квартире.")
        return
    unpaid = get_unpaid_charges(apartment["id"])
    if not unpaid:
        await message.answer("✅ Всё оплачено!")
        return
    text = "⚠️ Неоплаченные начисления:\n\n"
    for ch in unpaid:
        debt = ch["amount"] - ch["paid"]
        util = UTILITIES_RU.get(ch["utility_type"], ch["utility_type"])
        text += f"• {util} ({ch['period_end']}) — {debt:.2f} руб\n"
    await message.answer(text)


@router.message(Command("pay"))
async def cmd_pay(message: Message, state: FSMContext):
    apartment = get_resident_apartment(message.from_user.id)
    if not apartment:
        await message.answer("Сначала привяжитесь к квартире.")
        return
    unpaid = get_unpaid_charges(apartment["id"])
    if not unpaid:
        await message.answer("Нет долгов!")
        return
    buttons = [[InlineKeyboardButton(
        text=f"{UTILITIES_RU[ch['utility_type']]} ({ch['period_end']}) — {ch['amount'] - ch['paid']:.2f} руб",
        callback_data=f"pay1_{ch['id']}"
    )] for ch in unpaid]
    await message.answer("Выберите начисление:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(PayForChargeStates.choosing_charge)


@router.callback_query(PayForChargeStates.choosing_charge, F.data.startswith("pay1_"))
async def charge_selected(callback: CallbackQuery, state: FSMContext):
    charge_id = int(callback.data.split("_")[-1])
    await state.update_data(charge_id=charge_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount, utility_type, period_end FROM charge WHERE id = ?", (charge_id,))
    ch = cur.fetchone()
    cur.execute("SELECT IFNULL(SUM(amount), 0) FROM payment WHERE charge_id = ?", (charge_id,))
    paid = cur.fetchone()[0]
    conn.close()
    debt = ch["amount"] - paid
    util = UTILITIES_RU.get(ch["utility_type"], ch["utility_type"])
    await callback.message.edit_text(
        f"{util} ({ch['period_end']})\nДолг: {debt:.2f} руб\nВведите сумму:",
        reply_markup=None
    )
    await state.set_state(PayForChargeStates.entering_amount)


@router.message(PayForChargeStates.entering_amount)
async def amount_entered(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0: raise ValueError
    except:
        await message.answer("Некорректная сумма. Попробуйте снова:")
        return
    data = await state.get_data()
    charge_id = data["charge_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount FROM charge WHERE id = ?", (charge_id,))
    total = cur.fetchone()["amount"]
    cur.execute("SELECT IFNULL(SUM(amount), 0) FROM payment WHERE charge_id = ?", (charge_id,))
    paid = cur.fetchone()[0]
    debt = total - paid
    conn.close()
    if amount > debt + 0.01:
        await message.answer(f"Сумма превышает долг ({debt:.2f} руб).")
        return
    await state.update_data(amount=amount)
    await message.answer(
        f"Сумма: {amount:.2f} руб\nПодтвердить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm1")],
            [InlineKeyboardButton("📎 Прикрепить квитанцию", callback_data="attach_receipt")]
        ])
    )
    await state.set_state(PayForChargeStates.confirming)


@router.callback_query(PayForChargeStates.confirming, F.data == "confirm1")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resident_id = get_or_create_resident(callback.from_user.id)
    apartment = get_resident_apartment(callback.from_user.id)
    save_payment_for_charge(data["charge_id"], apartment["id"], data["amount"], resident_id)
    await callback.message.edit_text("✅ Оплата сохранена!")
    await state.clear()


@router.callback_query(PayForChargeStates.confirming, F.data == "attach_receipt")
async def request_receipt(callback: CallbackQuery):
    await callback.message.answer("Отправьте фото или PDF квитанции.")


@router.message(F.content_type.in_({'photo', 'document'}), PayForChargeStates.confirming)
async def receive_receipt(message: Message, state: FSMContext):
    if message.document:
        file = await bot.get_file(message.document.file_id)
        ext = os.path.splitext(message.document.file_name or "")[1] or ".pdf"
    else:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        ext = ".jpg"
    filename = f"{uuid4().hex}{ext}"
    filepath = os.path.join(MEDIA_ROOT, filename)
    await bot.download_file(file.file_path, filepath)
    await state.update_data(receipt_path=filepath)
    await message.answer("Квитанция получена! Подтвердите оплату:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton("✅ Подтвердить с квитанцией", callback_data="confirm1_receipt")]
                         ])
                         )


@router.callback_query(F.data == "confirm1_receipt")
async def confirm_with_receipt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resident_id = get_or_create_resident(callback.from_user.id)
    apartment = get_resident_apartment(callback.from_user.id)
    save_payment_for_charge(
        data["charge_id"], apartment["id"], data["amount"], resident_id,
        receipt_path=data.get("receipt_path")
    )
    await callback.message.edit_text("✅ Оплата с квитанцией сохранена!")
    await state.clear()


# === ВЕБ-ЛОГИН ===
from webapp.auth import create_session


@router.message(Command("web_login"))
async def cmd_web_login(message: Message):
    telegram_id = message.from_user.id
    apartment = get_resident_apartment(telegram_id)
    if not apartment or not is_admin(telegram_id, apartment["id"]):
        await message.answer("Только админ может получить доступ к веб-панели.")
        return
    token = create_session(telegram_id, apartment["id"])
    url = f"http://localhost:5000/?token={token}"  # Для локального запуска
    await message.answer(f"Ссылка для входа:\n{url}\n(Действует 24 часа)")


# === WEBHOOK SETUP ===
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)


async def on_shutdown(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)


def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(lambda app: on_startup(bot))
    app.on_shutdown.append(lambda app: on_shutdown(bot))

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


# === MAIN ===
async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
