"""Yahoo Finance üzerinden fiyat/hacim verisi çeker (BIST ve ABD piyasaları)."""

import logging

import pandas as pd
import yfinance as yf

import config

log = logging.getLogger(__name__)


def is_bist_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(".IS")


def market_of(ticker: str) -> str:
    return "BIST" if is_bist_ticker(ticker) else "ABD"


def currency_of(ticker: str) -> str:
    return "TRY" if is_bist_ticker(ticker) else "USD"


def _download(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        log.warning("Fiyat verisi alınamadı (%s, %s): %s", ticker, interval, exc)
        return None

    if df is None or df.empty:
        log.warning("Fiyat verisi boş döndü: %s (%s)", ticker, interval)
        return None

    # yfinance çoklu-ticker indirmelerinde MultiIndex kolon döndürebiliyor.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df.dropna()


def fetch_price_history(ticker: str) -> pd.DataFrame | None:
    """Bir hisse için GÜNLÜK OHLCV geçmişini döndürür (uzun vadeli analiz için)."""
    return _download(ticker, config.PRICE_HISTORY_PERIOD, "1d")


def fetch_intraday_price_history(ticker: str) -> pd.DataFrame | None:
    """Bir hisse için GÜN İÇİ (ör. 15 dakikalık) OHLCV geçmişini döndürür."""
    return _download(ticker, config.INTRADAY_PERIOD, config.INTRADAY_INTERVAL)


def fetch_latest_price(ticker: str) -> float | None:
    df = fetch_price_history(ticker)
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[-1])
