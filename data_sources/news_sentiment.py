"""Google News RSS üzerinden başlık toplayıp basit anahtar-kelime duyarlılığı hesaplar.

Bu bir NLP modeli değildir; sık geçen olumlu/olumsuz kelimelere bakarak kaba bir
yön tahmini üretir. Gürültülü olabilir, bu yüzden bileşik skorda düşük ağırlıkla
(config.WEIGHT_NEWS) kullanılır. BIST hisseleri için Türkçe, ABD hisseleri için
İngilizce sorgu ve kelime listesi kullanılır.
"""

import logging
from urllib.parse import quote

import feedparser
import requests

import config
from data_sources.price_data import is_bist_ticker

log = logging.getLogger(__name__)

POSITIVE_WORDS_TR = [
    "rekor", "yükseldi", "yükseliş", "arttı", "artış", "kazandı", "kâr",
    "büyüme", "büyüdü", "anlaşma", "ihracat rekoru", "hedef fiyat yükseltti",
    "temettü", "güçlü bilanço", "beklentilerin üzerinde", "genişleme",
    "yeni yatırım", "prim yaptı", "olumlu",
]

NEGATIVE_WORDS_TR = [
    "düştü", "düşüş", "zarar", "kayıp", "gerileme", "geriledi", "iflas",
    "soruşturma", "ceza", "kesinti", "daralma", "hedef fiyat düşürdü",
    "beklentilerin altında", "grev", "dava", "olumsuz", "sat tavsiyesi",
    "iptal",
]

POSITIVE_WORDS_EN = [
    "record", "surge", "surged", "soar", "soared", "rally", "rallied",
    "beats", "beat estimates", "upgrade", "upgraded", "growth", "profit",
    "buyback", "dividend hike", "strong earnings", "outperform",
    "price target raised", "expansion", "breakthrough", "bullish",
]

NEGATIVE_WORDS_EN = [
    "plunge", "plunged", "slump", "slumped", "tumble", "tumbled", "crash",
    "downgrade", "downgraded", "miss estimates", "misses estimates", "loss",
    "lawsuit", "investigation", "recall", "layoffs", "sell-off", "bearish",
    "price target cut", "warning", "fraud", "decline",
]


def _query_for(ticker: str) -> tuple[str, str, str]:
    """(sorgu, hl, gl) döndürür."""
    if is_bist_ticker(ticker):
        return ticker.replace(".IS", "") + " hisse", "tr", "TR"
    return ticker + " stock", "en-US", "US"


def fetch_headlines(ticker: str) -> list[str]:
    query, hl, gl = _query_for(ticker)
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
    try:
        # feedparser.parse(url) kendi başına zaman aşımı uygulamaz — yanıt vermeyen
        # bir sunucu botu süresiz asabilir. Bu yüzden önce requests ile (zaman
        # aşımlı) indirip ham içeriği feedparser'a veriyoruz.
        response = requests.get(url, timeout=config.NEWS_TIMEOUT_SECONDS)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as exc:
        log.warning("Haber akışı alınamadı (%s): %s", ticker, exc)
        return []

    entries = getattr(feed, "entries", []) or []
    return [e.title for e in entries[: config.NEWS_LOOKBACK_COUNT] if getattr(e, "title", None)]


def score_headlines(headlines: list[str], ticker: str = "") -> float:
    """Başlıkları -1..+1 aralığında bir duyarlılık skoruna çevirir."""
    if not headlines:
        return 0.0

    if is_bist_ticker(ticker):
        pos_words, neg_words = POSITIVE_WORDS_TR, NEGATIVE_WORDS_TR
    else:
        pos_words, neg_words = POSITIVE_WORDS_EN, NEGATIVE_WORDS_EN

    total = 0
    hits = 0
    for title in headlines:
        lowered = title.lower()
        pos = sum(1 for w in pos_words if w in lowered)
        neg = sum(1 for w in neg_words if w in lowered)
        if pos or neg:
            hits += 1
            total += pos - neg

    if hits == 0:
        return 0.0

    raw = total / hits
    return max(-1.0, min(1.0, raw))


def fetch_news_score(ticker: str) -> float:
    return score_headlines(fetch_headlines(ticker), ticker)
