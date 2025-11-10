# webapp/auth.py
import redis
import json
from datetime import datetime, timedelta
from decouple import config

# Получаем URL Redis из .env или используем локальный по умолчанию
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)


def create_session(telegram_id: int, apartment_id: int) -> str:
    """Создаёт сессию и возвращает токен"""
    from secrets import token_urlsafe
    token = token_urlsafe(32)
    payload = {
        "telegram_id": telegram_id,
        "apartment_id": apartment_id,
        "expires": (datetime.utcnow() + timedelta(days=1)).isoformat()
    }
    redis_client.setex(f"session:{token}", timedelta(days=1), json.dumps(payload))
    return token


def get_session(token: str):
    """Возвращает данные сессии или None, если недействительна"""
    data = redis_client.get(f"session:{token}")
    if not data:  # ← вот правильное завершённое условие
        return None
    payload = json.loads(data)
    if datetime.fromisoformat(payload["expires"]) < datetime.utcnow():
        redis_client.delete(f"session:{token}")
        return None
    return payload
