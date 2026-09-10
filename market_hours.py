"""BIST ve ABD piyasalarının şu an açık olup olmadığını belirler.

Not: Resmi tatiller hesaba katılmaz (basit bir yaklaşım) — sadece hafta içi
gün ve saat aralığına bakılır. Piyasa bir tatil günü kapalıysa bot yine de
taramaya çalışır; o gün için borsadan veri gelmez, mevcut hata toleransı
(boş/eksik veri -> o hisse atlanır) zaten bunu güvenle idare eder.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

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
    if now.weekday() >= 5:
        return False
    return US_OPEN <= now.time() <= US_CLOSE


def open_markets() -> list[str]:
    markets = []
    if is_bist_open():
        markets.append("BIST")
    if is_us_open():
        markets.append("ABD")
    return markets
