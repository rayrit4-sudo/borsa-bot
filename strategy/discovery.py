"""Geniş piyasa evreninde günde bir kez çalışan keşif taraması.

İki aşamalı huni: önce ucuz bir teknik ön-eleme (sadece fiyat verisi, tüm
evren için) yapılır, sonra sadece en güçlü teknik adaylar (DISCOVERY_SHORTLIST_SIZE
kadar) için pahalı tam analiz (temel + haber + uzun vadeli) çalıştırılır. Bu,
yüzlerce hisse için gereksiz yere Yahoo/Google'a fundamentals/news isteği
atmayı önler — hız sınırına takılma riskini büyük ölçüde azaltır.

Sonuç: en iyi DISCOVERY_TOP_N aday, gün içi döngünün okuyacağı
ACTIVE_WATCHLIST_FILE'a yazılır (çekirdek WATCHLIST/US_WATCHLIST'e ek olarak).
"""

import json
import logging
import os
from datetime import date

import config
from data_sources import price_data
from strategy.scorer import analyze_ticker, technical_score

log = logging.getLogger(__name__)


def _core_tickers() -> set[str]:
    return set(config.WATCHLIST) | set(config.US_WATCHLIST)


def _technical_prefilter(universe: list[str]) -> list[str]:
    """Sadece fiyat verisiyle (ucuz) her hisseye teknik skor verir, en iyi
    DISCOVERY_SHORTLIST_SIZE kadarını döndürür."""
    scored = []
    consecutive_failures = 0
    for ticker in universe:
        df = price_data.fetch_price_history(ticker)
        if df is None or df.empty:
            consecutive_failures += 1
            if consecutive_failures >= config.CONSECUTIVE_FAILURE_ABORT_LIMIT:
                log.error(
                    "Ön-elemede art arda %d hisse başarısız oldu — muhtemelen "
                    "sistemik bir ağ sorunu var, ön-eleme burada durduruluyor.",
                    consecutive_failures,
                )
                break
            continue
        consecutive_failures = 0
        tech, _ = technical_score(df)
        scored.append((ticker, tech))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[: config.DISCOVERY_SHORTLIST_SIZE]]


def run_discovery() -> list[dict]:
    """Geniş evreni tarar, en iyi adayları bulur ve ACTIVE_WATCHLIST_FILE'a yazar.
    Döndürdüğü liste, bulunan adayların tam analiz sonuçlarıdır (loglama/rapor için)."""
    core = _core_tickers()
    universe = [
        t for t in (config.DISCOVERY_BIST_UNIVERSE + config.DISCOVERY_US_UNIVERSE)
        if t not in core
    ]

    log.info("Keşif taraması başlıyor: %d hisselik geniş evren (ön-eleme)...", len(universe))
    shortlist = _technical_prefilter(universe)
    log.info("Ön-elemeden %d aday geçti, tam analiz yapılıyor...", len(shortlist))

    candidates = []
    consecutive_failures = 0
    for ticker in shortlist:
        try:
            result = analyze_ticker(ticker)
        except Exception as exc:
            log.warning("Keşif analizi başarısız (%s): %s", ticker, exc)
            result = None

        if result is not None:
            candidates.append(result)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= config.CONSECUTIVE_FAILURE_ABORT_LIMIT:
                log.error("Tam analizde art arda çok fazla hata — keşif burada durduruluyor.")
                break

    candidates.sort(key=lambda r: r["composite_score"], reverse=True)
    top = [c for c in candidates if c["composite_score"] >= config.DISCOVERY_MIN_SCORE]
    top = top[: config.DISCOVERY_TOP_N]

    _save_active_watchlist(top)

    log.info(
        "Keşif tamamlandı: %d aday bulundu (skor >= %.2f), çekirdek listeye eklendi.",
        len(top), config.DISCOVERY_MIN_SCORE,
    )
    for c in top:
        log.info("  + %s [%s] skor=%.2f sinyal=%s", c["ticker"], c["market"], c["composite_score"], c["signal"])

    return top


def _save_active_watchlist(candidates: list[dict]) -> None:
    data = {
        "date": date.today().isoformat(),
        "discovered": [
            {"ticker": c["ticker"], "market": c["market"], "composite_score": c["composite_score"]}
            for c in candidates
        ],
    }
    with open(config.ACTIVE_WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_discovered_tickers() -> list[str]:
    """main.py'nin gün içi döngüsü tarafından kullanılır: bugüne ait keşfedilmiş
    adayların ticker listesini döndürür (yoksa veya bugüne ait değilse boş liste)."""
    if not os.path.exists(config.ACTIVE_WATCHLIST_FILE):
        return []
    try:
        with open(config.ACTIVE_WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log.warning("Aktif izleme listesi okunamadı: %s", exc)
        return []

    if data.get("date") != date.today().isoformat():
        return []
    return [d["ticker"] for d in data.get("discovered", [])]
