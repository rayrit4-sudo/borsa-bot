"""BIST + ABD kağıt (sanal) alım-satım botu — GÜN İÇİ (intraday) mod.

Görev Zamanlayıcı ile piyasalar açıkken 15 dakikada bir çalıştırılır.
Çalıştığında:
1) Hangi piyasaların (BIST / ABD) şu an açık olduğunu belirler; hiçbiri açık
   değilse hiçbir ağ isteği yapmadan çıkar
2) Açık piyasa(lar)daki hisseler için TAZE gün içi (15dk mum) teknik skor
   hesaplar; temel + uzun vadeli (dolar bazlı) + haber skorları gün içinde
   değişmediği için günde bir kez hesaplanıp önbellekten okunur
   (strategy/slow_scores.py) — ABD hisseleri güncel USDTRY kuruyla TL
   karşılığına çevrilip aynı tek (TL bazlı) portföyden işlem görür
3) Skorları sıralı bir tabloda gösterir
4) Açık pozisyonlarda stop-loss / iz süren (trailing) stop kontrolü yapar
5) SAT sinyali olan açık pozisyonları kapatır; piyasa rejimi (BIST için XU100,
   ABD için S&P 500) ayı değilse ve portföy zarar kesici tetiklenmemişse,
   AL sinyali olan en güçlü adaylara (sektör/piyasa/risk limitleri dahilinde)
   sanal alım yapar
6) Güncel portföy durumunu ekrana yazar ve durumu diske kaydeder

Bu bot GERÇEK PARAYLA İŞLEM YAPMAZ. Sadece simülasyon amaçlıdır.
Gerçek bir aracı kurum API'sine bağlanmadan önce sonuçları uzun süre
gözlemleyip stratejiyi doğrulaman önerilir.
"""

import logging
import os
import sys
from datetime import datetime

import config
import market_hours
from data_sources import price_data
from portfolio.paper_broker import PaperBroker
from strategy import discovery, slow_scores
from strategy.scorer import market_regime, rank_watchlist_intraday

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


class _Tee:
    """Aynı çıktıyı hem konsola hem log dosyasına yazar (zamanlanmış görev
    çalışırken konsol olmasa da her çalıştırma diske kaydedilsin diye)."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)

    def flush(self):
        for s in self._streams:
            s.flush()


_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_log_fp = open(os.path.join(_LOG_DIR, f"bot_{datetime.now():%Y-%m-%d}.log"), "a", encoding="utf-8")
sys.stdout = _Tee(sys.stdout, _log_fp)
sys.stderr = _Tee(sys.stderr, _log_fp)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def print_ranking(results: list[dict]) -> None:
    header = (
        f"{'HİSSE':<10}{'PİYASA':<7}{'FİYAT(TL)':>11}{'TEKNİK':>9}{'TEMEL':>8}{'HABER':>8}"
        f"{'UZUN VD':>9}{'BİLEŞİK':>9}{'SİNYAL':>8}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['ticker']:<10}{r['market']:<7}{r['last_price']:>11.2f}{r['technical_score']:>9.2f}"
            f"{r['fundamental_score']:>8.2f}{r['news_score']:>8.2f}"
            f"{r['long_term_score']:>9.2f}{r['composite_score']:>9.2f}{r['signal']:>8}"
        )


def main() -> None:
    open_markets = market_hours.open_markets()
    if not open_markets:
        log.info(
            "Piyasalar kapalı (BIST: %s, ABD: %s) — bu taramada işlem yapılmadı.",
            "açık" if market_hours.is_bist_open() else "kapalı",
            "açık" if market_hours.is_us_open() else "kapalı",
        )
        return

    # Çekirdek liste + o günün geniş keşif taramasından (discovery.py) gelen
    # adaylar birlikte, sadece o an açık olan piyasa(lar)a ait olanlar taranır.
    discovered = discovery.load_discovered_tickers()
    all_bist = config.WATCHLIST + [t for t in discovered if price_data.is_bist_ticker(t)]
    all_us = config.US_WATCHLIST + [t for t in discovered if not price_data.is_bist_ticker(t)]

    watchlist = []
    if "BIST" in open_markets:
        watchlist += all_bist
    if "ABD" in open_markets:
        watchlist += all_us

    log.info(
        "Açık piyasa(lar): %s — %d hisse taranıyor (%d keşif adayı dahil)...",
        ", ".join(open_markets), len(watchlist), len(discovered),
    )

    # Temel/uzun vadeli/haber skorları (gün içinde değişmez) günde bir kez
    # hesaplanır; her iki piyasanın da tüm listesi (keşif adayları dahil) için
    # (o an kapalı olan piyasa dahil) önbelleğe alınır ki piyasa açıldığında hazır olsun.
    slow = slow_scores.get_slow_scores(all_bist + all_us)

    results = rank_watchlist_intraday(watchlist, slow)

    if not results:
        log.error("Hiçbir hisse için veri alınamadı. İnternet bağlantısını kontrol et.")
        return

    coverage = len(results) / len(watchlist)
    if coverage < config.MIN_DATA_COVERAGE_PCT:
        log.error(
            "Veri kalitesi yetersiz: %d/%d hisse (%.0f%%) alınabildi (eşik: %.0f%%). "
            "Muhtemelen geçici bir ağ/API sorunu var. Bu çalıştırmada hiçbir alım/satım/"
            "değerleme yapılmayacak — mevcut portföy son bilinen haliyle korunuyor.",
            len(results), len(watchlist), coverage * 100, config.MIN_DATA_COVERAGE_PCT * 100,
        )
        broker = PaperBroker()
        print("\n=== SON BİLİNEN PORTFÖY DURUMU (bugünkü fiyatlarla güncellenmedi) ===")
        print(f"Nakit: {broker.cash:,.2f} TL")
        if broker.positions:
            for ticker, pos in broker.positions.items():
                print(f"  {ticker} [{pos.get('sector', '?')}]: {pos['qty']} adet @ ort. {pos['avg_price']:.2f} TL")
        else:
            print("Açık pozisyon yok.")
        return

    current_prices = {r["ticker"]: r["last_price"] for r in results}
    by_ticker = {r["ticker"]: r for r in results}

    print("\n=== SKOR TABLOSU ===")
    print_ranking(results)

    # Bir piyasanın rejim skoru sadece o piyasa açıkken (yeni alım kararında)
    # kullanılır — kapalıyken gereksiz yere 5 yıllık günlük veri çekmeyelim.
    def regime_label(score: float) -> str:
        return "AYI (düşüş trendi)" if score <= config.MARKET_REGIME_BEARISH_THRESHOLD else "normal/yükseliş"

    regime_by_market: dict[str, float] = {}
    if "BIST" in open_markets:
        bist_regime_score, _ = market_regime(config.BIST_REGIME_INDEX)
        regime_by_market["BIST"] = bist_regime_score
        print(f"\nPiyasa rejimi BIST ({config.BIST_REGIME_INDEX}): skor {bist_regime_score:+.2f} -> {regime_label(bist_regime_score)}")
    if "ABD" in open_markets:
        us_regime_score, _ = market_regime(config.US_REGIME_INDEX)
        regime_by_market["ABD"] = us_regime_score
        print(f"Piyasa rejimi ABD ({config.US_REGIME_INDEX}): skor {us_regime_score:+.2f} -> {regime_label(us_regime_score)}")

    broker = PaperBroker()
    broker.backfill_metadata(by_ticker)
    broker.update_peak_equity(current_prices)

    # 1) Önce mevcut pozisyonlarda stop-loss / iz süren (trailing) stop kontrolü
    broker.manage_open_positions(current_prices)

    # 2) SAT sinyali olan açık pozisyonları kapat
    for ticker in list(broker.positions.keys()):
        r = by_ticker.get(ticker)
        if r and r["signal"] == "SAT":
            broker.sell(ticker, r["last_price"], reason="SAT sinyali")

    # 3) Yeni alım yapmadan önce portföy düzeyinde risk-off kontrolü
    #    (piyasa rejimi ayı ise ilgili piyasadan alım zaten aşağıda engellenir).
    risk_off, drawdown = broker.is_risk_off(current_prices)
    if risk_off:
        print(f"\nYeni pozisyon açılmıyor: portföy zirveden {drawdown:+.1%} gerilemiş (drawdown kesici aktif)")
    else:
        # AL sinyali olan en güçlü adaylara sanal alım yap (limitler dahilinde)
        for r in results:
            if r["signal"] != "AL":
                continue
            if len(broker.positions) >= config.MAX_OPEN_POSITIONS:
                break
            if regime_by_market.get(r["market"], 0.0) <= config.MARKET_REGIME_BEARISH_THRESHOLD:
                continue  # bu piyasa ayı trendinde, yeni alım yapılmıyor
            broker.buy(
                r["ticker"], r["last_price"], r["sector"], r["market"], r["currency"], r["native_price"],
                current_prices, reason=f"AL sinyali (skor {r['composite_score']:.2f})",
            )

    broker.update_peak_equity(current_prices)
    broker.save()

    print("\n=== PORTFÖY DURUMU ===")
    for line in broker.summary_lines(current_prices):
        print(line)

    print(f"\nİşlem kayıtları: {config.TRADE_LOG_FILE}")
    print(f"Portföy durumu: {config.STATE_FILE}")


if __name__ == "__main__":
    main()
