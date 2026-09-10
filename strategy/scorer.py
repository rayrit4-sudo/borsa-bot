"""Teknik + temel + haber sinyallerini birleştirip -1..+1 aralığında bir
bileşik skor ve AL/SAT/BEKLE kararı üretir."""

import logging

import pandas as pd

import config
from data_sources import fundamentals, fx, news_sentiment, price_data
from strategy import indicators

log = logging.getLogger(__name__)


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def technical_score(df: pd.DataFrame) -> tuple[float, dict]:
    close = df["Close"]
    volume = df["Volume"]

    sma_short = indicators.sma(close, config.SMA_SHORT)
    sma_long = indicators.sma(close, config.SMA_LONG)
    rsi_series = indicators.rsi(close)
    _, _, macd_hist = indicators.macd(close)
    vol_ratio = indicators.volume_spike_ratio(volume)

    if len(close) < config.SMA_LONG + 1 or pd.isna(sma_long.iloc[-1]):
        return 0.0, {"insufficient_history": True}

    last_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    last_rsi = rsi_series.iloc[-1]
    last_hist = macd_hist.iloc[-1]
    last_vol_ratio = vol_ratio.iloc[-1]

    ma_score = 1.0 if sma_short.iloc[-1] > sma_long.iloc[-1] else -1.0

    # RSI_OVERSOLD'da (veya altında) +1, RSI_OVERBOUGHT'ta (veya üstünde) -1,
    # ortalarında (50) 0 olacak şekilde doğrusal ölçekleme.
    rsi_midpoint = (config.RSI_OVERSOLD + config.RSI_OVERBOUGHT) / 2
    rsi_half_range = (config.RSI_OVERBOUGHT - config.RSI_OVERSOLD) / 2
    rsi_score = _clip((rsi_midpoint - last_rsi) / rsi_half_range) if pd.notna(last_rsi) else 0.0

    macd_score = 1.0 if last_hist > 0 else -1.0

    if pd.notna(last_vol_ratio) and last_vol_ratio >= config.VOLUME_SPIKE_RATIO:
        volume_score = 0.5 if last_close > prev_close else -0.5
    else:
        volume_score = 0.0

    score = _clip(
        0.30 * ma_score
        + 0.25 * rsi_score
        + 0.25 * macd_score
        + 0.20 * volume_score
    )

    details = {
        "sma_short": round(float(sma_short.iloc[-1]), 2),
        "sma_long": round(float(sma_long.iloc[-1]), 2),
        "rsi": round(float(last_rsi), 1) if pd.notna(last_rsi) else None,
        "macd_hist": round(float(last_hist), 4),
        "volume_ratio": round(float(last_vol_ratio), 2) if pd.notna(last_vol_ratio) else None,
    }
    return score, details


def _linear_score(value, best: float, worst: float) -> float:
    if best == worst:
        return 0.0
    t = (value - worst) / (best - worst)
    t = max(0.0, min(1.0, t))
    return t * 2 - 1


# (alan_adı, en_iyi_değer, en_kötü_değer)
_FUNDAMENTAL_RULES = {
    "trailingPE": (8.0, 40.0),
    "priceToBook": (0.8, 6.0),
    "returnOnEquity": (0.30, -0.10),
    "profitMargins": (0.20, -0.10),
    "revenueGrowth": (0.30, -0.10),
    "debtToEquity": (30.0, 200.0),
    "earningsGrowth": (0.30, -0.20),
}


def fundamental_score(raw: dict) -> tuple[float, dict]:
    if not raw:
        return 0.0, {"insufficient_data": True}

    sub_scores = {}
    for field, (best, worst) in _FUNDAMENTAL_RULES.items():
        value = raw.get(field)
        if value is None:
            continue
        if field == "trailingPE" and value <= 0:
            sub_scores[field] = -1.0
            continue
        sub_scores[field] = _linear_score(value, best, worst)

    if not sub_scores:
        return 0.0, {"insufficient_data": True}

    score = _clip(sum(sub_scores.values()) / len(sub_scores))
    return score, sub_scores


def long_term_score(df: pd.DataFrame, fx_series: pd.Series | None, currency: str = "TRY") -> tuple[float, dict]:
    """Dolar bazlı (kur etkisinden arındırılmış) çok yıllı getiriye bakar.

    Gerekçe: BIST'te TL getiri, TL'nin değer kaybı yüzünden neredeyse her
    hissede büyük görünür. Fiyatı USDTRY'ye bölüp gerçek (dolar) CAGR'a
    bakmak, gerçekten değer yaratan şirketleri ayırt eder. ABD hisseleri
    zaten dolar bazlı olduğu için kur çevrimi yapılmaz.
    """
    close = df["Close"].dropna()
    if len(close) < 2:
        return 0.0, {"insufficient_data": True}

    start_date = close.index[0]
    end_date = close.index[-1]
    years = (end_date - start_date).days / 365.25
    if years < config.LONG_TERM_MIN_YEARS:
        return 0.0, {"insufficient_history_years": round(years, 1)}

    if currency == "USD":
        usd_start = float(close.iloc[0])
        usd_end = float(close.iloc[-1])
    else:
        if fx_series is None:
            return 0.0, {"insufficient_data": True}
        fx_start = fx.rate_near(fx_series, start_date)
        fx_end = fx.rate_near(fx_series, end_date)
        if not fx_start or not fx_end:
            return 0.0, {"insufficient_data": True}
        usd_start = float(close.iloc[0]) / fx_start
        usd_end = float(close.iloc[-1]) / fx_end

    usd_cagr_pct = ((usd_end / usd_start) ** (1 / years) - 1) * 100

    score = _linear_score(usd_cagr_pct, config.LONG_TERM_BEST_CAGR_PCT, config.LONG_TERM_WORST_CAGR_PCT)
    return score, {"years": round(years, 1), "usd_cagr_pct": round(usd_cagr_pct, 1)}


def _combine(
    ticker: str, market: str, currency: str, native_price: float, fx_rate: float | None,
    tech: float, tech_details: dict, fund: float, fund_details: dict,
    news: float, news_headline_count: int, long_term: float, long_term_details: dict,
    sector: str,
) -> dict | None:
    """Teknik + temel + haber + uzun vadeli skorları birleştirip sonuç sözlüğü üretir.
    Hem günlük (analyze_ticker) hem gün içi (analyze_ticker_intraday) tarafından kullanılır."""
    composite = _clip(
        config.WEIGHT_TECHNICAL * tech
        + config.WEIGHT_FUNDAMENTAL * fund
        + config.WEIGHT_NEWS * news
        + config.WEIGHT_LONG_TERM * long_term
    )

    if composite >= config.BUY_THRESHOLD:
        signal = "AL"
    elif composite <= config.SELL_THRESHOLD:
        signal = "SAT"
    else:
        signal = "BEKLE"

    if currency == "USD":
        if not fx_rate:
            log.warning("USDTRY kuru alınamadığı için %s atlandı", ticker)
            return None
        price_tl = native_price * fx_rate
    else:
        price_tl = native_price

    return {
        "ticker": ticker,
        "market": market,
        "currency": currency,
        "native_price": native_price,
        "last_price": price_tl,  # TL karşılığı — portföy bu birimde çalışır
        "technical_score": round(tech, 3),
        "technical_details": tech_details,
        "fundamental_score": round(fund, 3),
        "fundamental_details": fund_details,
        "news_score": round(news, 3),
        "news_headline_count": news_headline_count,
        "long_term_score": round(long_term, 3),
        "long_term_details": long_term_details,
        "sector": sector,
        "composite_score": round(composite, 3),
        "signal": signal,
    }


def analyze_ticker(ticker: str) -> dict | None:
    """Tam (günlük) analiz: teknik + temel + haber + uzun vadeli skorların hepsi
    taze hesaplanır. Yavaş skorları önbelleğe almak isteyen gün içi tarama için
    analyze_ticker_intraday()'i kullan."""
    df = price_data.fetch_price_history(ticker)
    if df is None or df.empty:
        return None

    currency = price_data.currency_of(ticker)
    market = price_data.market_of(ticker)

    tech, tech_details = technical_score(df)
    fund_raw = fundamentals.fetch_fundamentals(ticker)
    fund, fund_details = fundamental_score(fund_raw)
    headlines = news_sentiment.fetch_headlines(ticker)
    news = news_sentiment.score_headlines(headlines, ticker)
    fx_series = fx.fetch_usdtry_history()
    long_term, long_term_details = long_term_score(df, fx_series, currency)

    native_price = float(df["Close"].iloc[-1])
    fx_rate = fx.latest_rate(fx_series) if currency == "USD" else None

    return _combine(
        ticker, market, currency, native_price, fx_rate,
        tech, tech_details, fund, fund_details,
        news, len(headlines), long_term, long_term_details,
        fund_raw.get("sector", "Bilinmiyor"),
    )


def analyze_ticker_intraday(ticker: str, slow: dict) -> dict | None:
    """Gün içi analiz: teknik skor taze gün içi mum verisiyle hesaplanır; temel/
    uzun vadeli/haber skorları (gün içinde değişmediği için) günlük önbellekten
    (strategy.slow_scores.get_slow_scores) alınır."""
    df = price_data.fetch_intraday_price_history(ticker)
    if df is None or df.empty:
        return None

    currency = price_data.currency_of(ticker)
    market = price_data.market_of(ticker)
    tech, tech_details = technical_score(df)

    native_price = float(df["Close"].iloc[-1])
    fx_rate = fx.latest_rate(fx.fetch_usdtry_history()) if currency == "USD" else None

    return _combine(
        ticker, market, currency, native_price, fx_rate,
        tech, tech_details,
        slow.get("fundamental_score", 0.0), {"source": "gunluk_onbellek"},
        slow.get("news_score", 0.0), 0,
        slow.get("long_term_score", 0.0), {"source": "gunluk_onbellek"},
        slow.get("sector", "Bilinmiyor"),
    )


def market_regime(index_ticker: str) -> tuple[float, dict]:
    """Verilen endeksin kendi teknik skoruna bakarak genel piyasa rejimini
    (yükseliş/düşüş trendi) belirler. Tek tek hisse sinyallerine güvenmeden
    önce genel rüzgarın yönünü bilmek için kullanılır."""
    df = price_data.fetch_price_history(index_ticker)
    if df is None or df.empty:
        log.warning(
            "Piyasa rejimi verisi alınamadı (%s) — bu piyasa için nötr (0.0) varsayılıyor, "
            "yani ayı-piyasası koruması bu çalıştırmada devre dışı kalabilir.",
            index_ticker,
        )
        return 0.0, {"insufficient_data": True}
    return technical_score(df)


def rank_watchlist(watchlist: list[str]) -> list[dict]:
    results = []
    consecutive_failures = 0
    for ticker in watchlist:
        try:
            result = analyze_ticker(ticker)
        except Exception as exc:
            log.warning("Analiz başarısız (%s): %s", ticker, exc)
            result = None

        if result is not None:
            results.append(result)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= config.CONSECUTIVE_FAILURE_ABORT_LIMIT:
                log.error(
                    "Art arda %d hisse başarısız oldu — muhtemelen sistemik bir ağ "
                    "sorunu var. Kalan tarama iptal ediliyor (10+ dakika beklemek yerine).",
                    consecutive_failures,
                )
                break

    results.sort(key=lambda r: r["composite_score"], reverse=True)
    return results


def rank_watchlist_intraday(watchlist: list[str], slow_scores: dict[str, dict]) -> list[dict]:
    results = []
    consecutive_failures = 0
    for ticker in watchlist:
        slow = slow_scores.get(ticker)
        if not slow:
            continue
        try:
            result = analyze_ticker_intraday(ticker, slow)
        except Exception as exc:
            log.warning("Gün içi analiz başarısız (%s): %s", ticker, exc)
            result = None

        if result is not None:
            results.append(result)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= config.CONSECUTIVE_FAILURE_ABORT_LIMIT:
                log.error(
                    "Art arda %d hisse başarısız oldu — muhtemelen sistemik bir ağ "
                    "sorunu var. Kalan tarama iptal ediliyor (10+ dakika beklemek yerine).",
                    consecutive_failures,
                )
                break

    results.sort(key=lambda r: r["composite_score"], reverse=True)
    return results
