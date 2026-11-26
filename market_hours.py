"""BIST ve ABD piyasalarının şu an açık olup olmadığını belirler.

BIST için hafta içi saatleri, ABD için bilinen tatil ve erken kapanış
takvimi kullanılır.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from strategy.orb_entry import NYSE_EARLY_CLOSE, NYSE_HOLIDAYS

BIST_TZ = ZoneInfo("Europe/Istanbul")
US_TZ = ZoneInfo("America/New_York")

BIST_OPEN = time(10, 0)
BIST_CLOSE = time(18, 0)
US_OPEN = time(9, 30)
US_CLOSE = time(16, 0)


def is_bist_open(now: datetime | None = None) -> bool:
    now = (now or datetime.now(BIST_TZ)).astimezone(BIST_TZ)
    if now.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
        return False
    return BIST_OPEN <= now.time() <= BIST_CLOSE


def is_us_open(now: datetime | None = None) -> bool:
    now = (now or datetime.now(US_TZ)).astimezone(US_TZ)
    if now.weekday() >= 5 or now.date().isoformat() in NYSE_HOLIDAYS:
        return False
    close = time(13, 0) if now.date().isoformat() in NYSE_EARLY_CLOSE else US_CLOSE
    return US_OPEN <= now.time() < close


def open_markets() -> list[str]:
    markets = []
    if is_bist_open():
        markets.append("BIST")
    if is_us_open():
        markets.append("ABD")
    return markets
