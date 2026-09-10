"""Temel analiz metrikleri (Yahoo Finance 'info' alanından).

Not: Yahoo Finance'in BIST şirketleri için temel veri kapsamı sınırlı olabilir.
Bir metrik mevcut değilse o metrik skora dahil edilmez (nötr sayılır), bu yüzden
skor eksik veriyle de tutarlı kalır.
"""

import logging

import yfinance as yf

log = logging.getLogger(__name__)


def fetch_fundamentals(ticker: str) -> dict:
    """Ham temel veri alanlarını döndürür. Alınamayanlar için anahtar olmaz."""
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception as exc:
        log.warning("Temel veri alınamadı (%s): %s", ticker, exc)
        return {}

    if not info:
        return {}

    fields = [
        "trailingPE",
        "priceToBook",
        "returnOnEquity",
        "profitMargins",
        "revenueGrowth",
        "debtToEquity",
        "earningsGrowth",
    ]
    result = {f: info.get(f) for f in fields if info.get(f) is not None}
    if info.get("sector"):
        result["sector"] = info["sector"]
    return result
