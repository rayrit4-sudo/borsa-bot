"""Günde bir kez çalışan geniş piyasa keşif taraması.

Görev Zamanlayıcı ile gün içi taramadan (main.py) ÖNCE, günde bir kez
çalıştırılır (ör. 09:00). Geniş bir hisse evrenini tarayıp en güçlü adayları
active_watchlist.json'a yazar; main.py bunları o gün boyunca çekirdek
izleme listesine ekler.
"""

import logging
import os
import sys
from datetime import datetime

from strategy.discovery import run_discovery

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


class _Tee:
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


if __name__ == "__main__":
    run_discovery()
