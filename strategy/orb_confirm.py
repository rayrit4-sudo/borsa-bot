"""Day-trader-skill entegrasyonu: ABD hisseleri için 'açılış aralığı kırılımı' teyidi.

Mantık: ABD hissesine AL sinyali gelse bile, hisse o günün ilk 15 dakikalık
aralığının (açılış aralığı) ÜSTÜNDE bir 5 dakikalık mum kapatmadıysa alınmaz.
Bu, temel/uzun vadeli skorların şişirdiği 'rastgele zamanlı' girişleri eler.
Veri: Yahoo ücretsiz 5dk mumlar. Veri alınamazsa güvenli tarafta kalıp alım yapılmaz.
Kaynak kod: strategy/orb_entry.py (day-trader-skill / trader-entry, MIT).
"""
import logging

from strategy import orb_entry

log = logging.getLogger(__name__)


def orb_confirmed(ticker: str, now_utc=None, offline=None) -> tuple[bool, str]:
    """(onay, açıklama) döner. Sadece ABD hisseleri için anlamlıdır."""
    try:
        now = now_utc or orb_entry.utc_now()
        chart = orb_entry.get_chart(
            ticker, "5m", orb_entry.to_eastern(now).date(), offline, orb_entry.to_eastern(orb_entry.utc_now()).date()
        )
        res = orb_entry.evaluate(chart, now, setup="orb", or_minutes=15, interval="5m")
    except Exception as e:  # ağ/veri hatası -> alım yok
        log.warning("ORB teyidi alınamadı (%s): %s", ticker, e)
        return False, f"veri alınamadı ({e})"
    status = res["status"]
    reason = res.get("reason") or ""
    if status != "triggered":
        return False, f"{status}: {reason}"
    orr = res.get("opening_range") or {}
    last = (res.get("last") or {}).get("close") if isinstance(res.get("last"), dict) else None
    high = orr.get("high")
    if last is not None and high is not None and last <= high:
        return False, f"kırılım oldu ama fiyat tekrar aralığın içine döndü ({last} <= {high})"
    return True, reason
