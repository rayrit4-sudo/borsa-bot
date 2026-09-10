"""Teknik gösterge hesaplamaları (harici TA kütüphanesi olmadan, pandas ile)."""

import pandas as pd

import config


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series):
    macd_line = ema(series, config.MACD_FAST) - ema(series, config.MACD_SLOW)
    signal_line = ema(macd_line, config.MACD_SIGNAL)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def volume_spike_ratio(volume: pd.Series) -> pd.Series:
    avg_vol = volume.rolling(window=config.VOLUME_LOOKBACK).mean()
    return volume / avg_vol.replace(0, pd.NA)
