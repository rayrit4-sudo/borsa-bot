"""USD/TRY kuru — uzun vadeli reel (dolar bazlı) getiri hesaplamak için.

Bir çalıştırma içinde tüm hisseler için tek seferlik çekilip önbellekte tutulur.
"""

import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

_cache: pd.Series | None = None
_fetch_attempted: bool = False


def fetch_usdtry_history() -> pd.Series | None:
    """USDTRY geçmişini çeker ve süreç boyunca önbellekte tutar.

    Hem başarı hem başarısızlık önbelleğe alınır — aksi halde kur çekimi
    başarısız olduğunda her hisse için (izleme listesindeki tüm hisseler
    boyunca) aynı isteği tekrar tekrar deneyip zaman kaybederdik.
    """
    global _cache, _fetch_attempted
    if _fetch_attempted:
        return _cache
    _fetch_attempted = True

    try:
        df = yf.download("USDTRY=X", period="10y", interval="1d", progress=False, auto_adjust=True)
    except Exception as exc:
        log.warning("USDTRY kuru alınamadı: %s", exc)
        return None

    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    _cache = df["Close"].dropna()
    return _cache


def rate_near(fx_series: pd.Series, date) -> float | None:
    """Verilen tarihe en yakın USDTRY kurunu döndürür."""
    if fx_series is None or fx_series.empty:
        return None
    idx = fx_series.index.get_indexer([date], method="nearest")[0]
    return float(fx_series.iloc[idx])


def latest_rate(fx_series: pd.Series | None) -> float | None:
    """En güncel USDTRY kurunu döndürür (ABD hisselerini TL'ye çevirmek için)."""
    if fx_series is None or fx_series.empty:
        return None
    return float(fx_series.iloc[-1])
