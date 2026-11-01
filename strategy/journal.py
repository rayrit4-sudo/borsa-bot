"""İşlem günlüğü: her kapanan işlemin hangi kuralla alındığını ve sonucunu tutar.

Amaç: bot hangi kuralın gerçekten para kazandırdığını kendi sonuçlarından öğrensin.
- docs/signal_journal.json : kapanan işlemler (kural, kâr/zarar %)
- docs/signal_stats.json   : kural başına özet (panel okur)
- size_multiplier(kural)   : yeterli işlem (MIN_TRADES) birikince pozisyon büyüklüğü çarpanı
"""
import json
import os
from datetime import datetime

import config


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def record_close(ticker: str, setup: str, pnl: float, cost_basis: float) -> None:
    """Satış anında çağrılır. Eski pozisyonlarda kural yoksa 'bilinmiyor' yazılır."""
    journal = _load(config.JOURNAL_FILE)
    journal.append({
        "t": datetime.now().isoformat(timespec="seconds"),
        "ticker": ticker,
        "setup": setup or "bilinmiyor",
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / cost_basis * 100, 3) if cost_basis else 0.0,
    })
    journal = journal[-2000:]
    os.makedirs(os.path.dirname(config.JOURNAL_FILE) or ".", exist_ok=True)
    with open(config.JOURNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False)
    _write_stats(journal)


def compute_stats(journal: list) -> dict:
    out = {}
    for j in journal:
        s = out.setdefault(j["setup"], {"n": 0, "wins": 0, "sum_pct": 0.0, "gross_win": 0.0, "gross_loss": 0.0})
        s["n"] += 1
        s["wins"] += 1 if j["pnl"] > 0 else 0
        s["sum_pct"] += j["pnl_pct"]
        if j["pnl"] > 0:
            s["gross_win"] += j["pnl"]
        else:
            s["gross_loss"] += -j["pnl"]
    for s in out.values():
        s["win_rate"] = round(s["wins"] / s["n"] * 100, 1)
        s["avg_pct"] = round(s["sum_pct"] / s["n"], 2)
        s["profit_factor"] = round(s["gross_win"] / s["gross_loss"], 2) if s["gross_loss"] else None
        s["multiplier"] = _multiplier(s["n"], s["avg_pct"])
        for k in ("sum_pct", "gross_win", "gross_loss"):
            s[k] = round(s[k], 2)
    return out


def _multiplier(n: int, avg_pct: float) -> float:
    if n < config.JOURNAL_MIN_TRADES:
        return 1.0   # yeterli veri yok: varsayılan büyüklük
    if avg_pct >= config.JOURNAL_GOOD_AVG_PCT:
        return config.JOURNAL_BOOST
    if avg_pct <= config.JOURNAL_BAD_AVG_PCT:
        return config.JOURNAL_CUT
    return 1.0


def _write_stats(journal: list) -> None:
    with open(config.SIGNAL_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump({"min_trades": config.JOURNAL_MIN_TRADES, "setups": compute_stats(journal)}, f, ensure_ascii=False, indent=2)


def size_multiplier(setup: str) -> float:
    s = compute_stats(_load(config.JOURNAL_FILE)).get(setup)
    return s["multiplier"] if s else 1.0
