"""Gün içinde değişmeyen (temel analiz + uzun vadeli dolar getirisi + haber)
skorları günde bir kez hesaplayıp diske önbelleğe alır.

Gün içi tarama her 15 dakikada bir çalıştığı için bu üç bileşeni her seferinde
yeniden hesaplamak hem gereksiz (temel veriler gün içinde değişmez) hem de
riskli (Yahoo/Google'a 43 hisse için günde ~55 kez istek atmak hız sınırına
takılmayı garantiler). Bunun yerine gün içindeki İLK taramada hesaplanır,
aynı takvim günü boyunca tekrar kullanılır.
"""

import json
import logging
import os
from datetime import date

import config
from data_sources import fundamentals, fx, news_sentiment, price_data
from strategy.scorer import fundamental_score, long_term_score

log = logging.getLogger(__name__)


def _load_cache() -> dict:
    if not os.path.exists(config.SLOW_SCORE_CACHE_FILE):
        return {}
    try:
        with open(config.SLOW_SCORE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Yavaş skor önbelleği okunamadı, sıfırdan hesaplanacak: %s", exc)
        return {}


def _save_cache(cache: dict) -> None:
    with open(config.SLOW_SCORE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_slow_scores(watchlist: list[str]) -> dict[str, dict]:
    """Her ticker için {fundamental_score, news_score, long_term_score, sector} döndürür.

    Bugüne ait önbellek varsa ve tüm ticker'ları içeriyorsa onu kullanır;
    değilse eksik olanları hesaplayıp önbelleğe ekler.
    """
    cache = _load_cache()
    today = date.today().isoformat()

    if cache.get("date") != today:
        cache = {"date": today, "tickers": {}}

    missing = [t for t in watchlist if t not in cache["tickers"]]
    if missing:
        log.info("Yavaş skorlar (temel/uzun vadeli/haber) hesaplanıyor: %d hisse...", len(missing))
        fx_series = fx.fetch_usdtry_history()
        consecutive_failures = 0
        for ticker in missing:
            success = False
            try:
                df = price_data.fetch_price_history(ticker)
                if df is not None and not df.empty:
                    currency = price_data.currency_of(ticker)
                    fund_raw = fundamentals.fetch_fundamentals(ticker)
                    fund, _ = fundamental_score(fund_raw)
                    headlines = news_sentiment.fetch_headlines(ticker)
                    news = news_sentiment.score_headlines(headlines, ticker)
                    lt, _ = long_term_score(df, fx_series, currency)
                    cache["tickers"][ticker] = {
                        "fundamental_score": fund,
                        "news_score": news,
                        "long_term_score": lt,
                        "sector": fund_raw.get("sector", "Bilinmiyor"),
                    }
                    success = True
            except Exception as exc:
                log.warning("Yavaş skor hesaplanamadı (%s): %s", ticker, exc)

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= config.CONSECUTIVE_FAILURE_ABORT_LIMIT:
                    log.error(
                        "Art arda %d hisse başarısız oldu — muhtemelen sistemik bir ağ "
                        "sorunu var. Kalan yavaş skor taraması iptal ediliyor (şimdiye "
                        "kadarki sonuçlar önbelleğe kaydedilecek).",
                        consecutive_failures,
                    )
                    break
        _save_cache(cache)

    return cache["tickers"]
