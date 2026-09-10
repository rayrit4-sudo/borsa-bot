"""Gerçek para kullanmayan, dosya tabanlı sanal (kağıt) alım-satım motoru.

Durum (nakit + açık pozisyonlar) JSON dosyasında saklanır, her çalıştırmada
kaldığı yerden devam eder. Tüm işlemler ayrıca CSV işlem defterine yazılır.

Risk kuralları (profesyonel yatırımcı pratiklerinden esinlenilmiştir):
- Riske dayalı pozisyon boyutlandırma: sabit % yerine, stop-loss'a çarparsa
  kaybedilecek tutar portföyün RISK_PER_TRADE_PCT'ini aşmaz.
- Sektör konsantrasyon limiti: aynı sektörden en fazla MAX_POSITIONS_PER_SECTOR pozisyon.
- Piyasa konsantrasyon limiti: BIST veya ABD'den en fazla MAX_POSITIONS_PER_MARKET pozisyon.
- İz süren stop (trailing stop): kazanan pozisyonlar sabit bir tavanda satılmaz,
  zirveden belirli bir yüzde geri çekilene kadar tutulur ("kazananı uzat").
- Ardışık kayıp soğuma süresi: art arda kayıplardan sonra risk otomatik küçülür.
- Portföy düzeyinde zarar kesici: toplam değer zirveden çok gerilerse yeni alım durur.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
from datetime import datetime

import config

log = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, state_file: str = config.STATE_FILE, trade_log_file: str | None = None):
        self.state_file = state_file
        # trade_log_file verilmezse state_file'dan türetilir — böylece farklı bir
        # state_file ile açılan (ör. test amaçlı) bir broker, gerçek işlem
        # defterine YANLIŞLIKLA yazamaz. Sadece varsayılan state_file kullanıldığında
        # varsayılan (gerçek) TRADE_LOG_FILE'a yazılır.
        if trade_log_file is not None:
            self.trade_log_file = trade_log_file
        elif state_file == config.STATE_FILE:
            self.trade_log_file = config.TRADE_LOG_FILE
        else:
            base, _ = os.path.splitext(state_file)
            self.trade_log_file = base + "_trades.csv"
        self.cash: float = config.INITIAL_CASH
        self.positions: dict[str, dict] = {}
        self.peak_equity: float = config.INITIAL_CASH
        self.consecutive_losses: int = 0
        self._load()

    # ---------- kalıcılık ----------

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.cash = state.get("cash", config.INITIAL_CASH)
            self.positions = state.get("positions", {})
            self.peak_equity = state.get("peak_equity", config.INITIAL_CASH)
            self.consecutive_losses = state.get("consecutive_losses", 0)
        except Exception as exc:
            log.warning("Portföy durumu okunamadı, sıfırdan başlanıyor: %s", exc)

    def save(self) -> None:
        state = {
            "cash": self.cash,
            "positions": self.positions,
            "peak_equity": self.peak_equity,
            "consecutive_losses": self.consecutive_losses,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _log_trade(
        self, action: str, ticker: str, qty: int, price: float, reason: str,
        commission: float = 0.0, pnl: float | None = None,
    ) -> None:
        is_new = not os.path.exists(self.trade_log_file)
        with open(self.trade_log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["timestamp", "action", "ticker", "qty", "price", "commission", "reason", "pnl", "cash_after"])
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                action, ticker, qty, round(price, 4), round(commission, 2), reason,
                round(pnl, 2) if pnl is not None else "",
                round(self.cash, 2),
            ])
        self._trim_trade_log()

    def _trim_trade_log(self) -> None:
        """İşlem defteri MAX_TRADE_LOG_ROWS'u aşarsa en eski satırları atar."""
        try:
            with open(self.trade_log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return

        if len(lines) <= config.MAX_TRADE_LOG_ROWS + 1:  # +1 başlık satırı
            return

        header, rows = lines[0], lines[1:]
        rows = rows[-config.MAX_TRADE_LOG_ROWS:]
        with open(self.trade_log_file, "w", encoding="utf-8") as f:
            f.writelines([header, *rows])

    def _sector_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for pos in self.positions.values():
            sector = pos.get("sector", "Bilinmiyor")
            counts[sector] = counts.get(sector, 0) + 1
        return counts

    def _market_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for pos in self.positions.values():
            market = pos.get("market", "Bilinmiyor")
            counts[market] = counts.get(market, 0) + 1
        return counts

    def backfill_metadata(self, results_by_ticker: dict[str, dict]) -> None:
        """Eski (sektör/piyasa bilgisi olmayan) pozisyonları günceller."""
        for ticker, pos in self.positions.items():
            r = results_by_ticker.get(ticker)
            if not r:
                continue
            pos.setdefault("sector", r.get("sector", "Bilinmiyor"))
            pos.setdefault("market", r.get("market", "Bilinmiyor"))
            pos.setdefault("currency", r.get("currency", "TRY"))

    # ---------- işlemler ----------

    def buy(
        self, ticker: str, price: float, sector: str, market: str, currency: str,
        native_price: float, current_prices: dict[str, float], reason: str = "AL sinyali",
    ) -> bool:
        if ticker in self.positions:
            return False
        if len(self.positions) >= config.MAX_OPEN_POSITIONS:
            return False
        if price <= 0:
            return False
        if self._sector_counts().get(sector, 0) >= config.MAX_POSITIONS_PER_SECTOR:
            log.info("ATLANDI (sektör limiti doldu): %s [%s]", ticker, sector)
            return False
        if self._market_counts().get(market, 0) >= config.MAX_POSITIONS_PER_MARKET:
            log.info("ATLANDI (piyasa limiti doldu): %s [%s]", ticker, market)
            return False

        equity = self.portfolio_value(current_prices)
        risk_multiplier = (
            config.COOLDOWN_RISK_MULTIPLIER
            if self.consecutive_losses >= config.CONSECUTIVE_LOSS_COOLDOWN
            else 1.0
        )
        risk_amount = equity * config.RISK_PER_TRADE_PCT * risk_multiplier
        stop_distance = price * config.STOP_LOSS_PCT
        if stop_distance <= 0:
            return False

        qty = math.floor(risk_amount / stop_distance)
        qty = min(qty, math.floor(equity * config.MAX_POSITION_PCT_OF_EQUITY / price))
        qty = min(qty, math.floor(self.cash / (price * (1 + config.COMMISSION_RATE))))
        if qty < 1:
            return False

        cost = qty * price
        commission = cost * config.COMMISSION_RATE
        total_cost = cost + commission
        if total_cost > self.cash:
            return False

        self.cash -= total_cost
        self.positions[ticker] = {
            "qty": qty,
            "avg_price": price,
            "sector": sector,
            "market": market,
            "currency": currency,
            "entry_native_price": native_price,
            "peak_price": price,
            "cost_basis": total_cost,
            "opened_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._log_trade("BUY", ticker, qty, price, reason, commission=commission)
        note = " [risk azaltıldı: kayıp serisi]" if risk_multiplier < 1.0 else ""
        log.info("ALINDI: %s x%d @ %.2f TL (%.2f TL + %.2f TL komisyon)%s", ticker, qty, price, cost, commission, note)
        return True

    def sell(self, ticker: str, price: float, reason: str = "SAT sinyali") -> bool:
        position = self.positions.get(ticker)
        if not position:
            return False

        qty = position["qty"]
        cost_basis = position.get("cost_basis", qty * position["avg_price"])
        proceeds = qty * price
        commission = proceeds * config.COMMISSION_RATE
        net_proceeds = proceeds - commission
        pnl = net_proceeds - cost_basis

        self.cash += net_proceeds
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else 0
        del self.positions[ticker]
        self._log_trade("SELL", ticker, qty, price, reason, commission=commission, pnl=pnl)
        log.info("SATILDI: %s x%d @ %.2f (net PnL: %.2f TL) — sebep: %s", ticker, qty, price, pnl, reason)
        return True

    def manage_open_positions(self, current_prices: dict[str, float]) -> None:
        """Stop-loss ve iz süren (trailing) stop kontrolü.

        Sabit bir kâr tavanında satmak yerine, pozisyon belirli bir kâra
        ulaştıktan sonra zirve fiyatı takip edilir ve fiyat zirveden
        TRAILING_STOP_PCT kadar gerilerse satılır — böylece güçlü trendler
        erken kesilmez ("kazananı uzat, kaybedeni kısa kes").
        """
        for ticker in list(self.positions.keys()):
            price = current_prices.get(ticker)
            if price is None:
                continue
            pos = self.positions[ticker]
            avg_price = pos["avg_price"]

            peak = max(pos.get("peak_price", avg_price), price)
            pos["peak_price"] = peak

            change_from_entry = (price / avg_price) - 1
            if change_from_entry <= -config.STOP_LOSS_PCT:
                self.sell(ticker, price, reason=f"stop-loss ({change_from_entry:+.1%})")
                continue

            peak_gain = (peak / avg_price) - 1
            if peak_gain >= config.TRAILING_STOP_ACTIVATION_PCT:
                drawdown_from_peak = (price / peak) - 1
                if drawdown_from_peak <= -config.TRAILING_STOP_PCT:
                    self.sell(
                        ticker, price,
                        reason=f"trailing-stop (zirve {peak:.2f} TL, zirveden {drawdown_from_peak:+.1%})",
                    )

    def update_peak_equity(self, current_prices: dict[str, float]) -> float:
        value = self.portfolio_value(current_prices)
        self.peak_equity = max(self.peak_equity, value)
        return value

    def is_risk_off(self, current_prices: dict[str, float]) -> tuple[bool, float]:
        value = self.portfolio_value(current_prices)
        if self.peak_equity <= 0:
            return False, 0.0
        drawdown = (value / self.peak_equity) - 1
        return drawdown <= -config.MAX_PORTFOLIO_DRAWDOWN_PCT, drawdown

    # ---------- raporlama ----------

    def portfolio_value(self, current_prices: dict[str, float]) -> float:
        value = self.cash
        for ticker, pos in self.positions.items():
            price = current_prices.get(ticker, pos["avg_price"])
            value += pos["qty"] * price
        return value

    def summary_lines(self, current_prices: dict[str, float]) -> list[str]:
        lines = []
        total_value = self.portfolio_value(current_prices)
        total_return = (total_value / config.INITIAL_CASH - 1) * 100
        drawdown = (total_value / self.peak_equity - 1) * 100 if self.peak_equity else 0.0

        lines.append(f"Nakit: {self.cash:,.2f} TL")
        lines.append(f"Portföy toplam değeri: {total_value:,.2f} TL  (başlangıç: {config.INITIAL_CASH:,.2f} TL, getiri: {total_return:+.2f}%)")
        lines.append(f"Zirveden uzaklık (drawdown): {drawdown:+.2f}%  (zirve: {self.peak_equity:,.2f} TL)")
        if self.consecutive_losses >= config.CONSECUTIVE_LOSS_COOLDOWN:
            lines.append(f"UYARI: {self.consecutive_losses} ardışık kayıp — yeni pozisyonlarda risk yarıya indirildi.")

        if not self.positions:
            lines.append("Açık pozisyon yok.")
            return lines

        lines.append("Açık pozisyonlar:")
        for ticker, pos in self.positions.items():
            price = current_prices.get(ticker, pos["avg_price"])
            unrealized_pct = (price / pos["avg_price"] - 1) * 100
            peak = pos.get("peak_price", pos["avg_price"])
            trailing_note = " [iz süren stop aktif]" if (peak / pos["avg_price"] - 1) >= config.TRAILING_STOP_ACTIVATION_PCT else ""
            if pos.get("currency") == "USD" and pos.get("entry_native_price"):
                currency_note = f" [giriş: ${pos['entry_native_price']:.2f}]"
            else:
                currency_note = ""
            lines.append(
                f"  {ticker} [{pos.get('sector', '?')} / {pos.get('market', '?')}]{currency_note}: "
                f"{pos['qty']} adet @ ort. {pos['avg_price']:.2f} TL "
                f"-> güncel {price:.2f} TL ({unrealized_pct:+.2f}%){trailing_note}"
            )
        return lines
