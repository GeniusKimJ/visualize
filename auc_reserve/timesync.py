"""NTP / 사이트 서버 시간 보정 (표준 라이브러리만 사용)."""
import logging
import socket
import statistics
import struct
import time
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime

from schedule import KST

log = logging.getLogger("timesync")
NTP_EPOCH = 2208988800


def ntp_offset(server="time.google.com", timeout=3.0):
    """(NTP 시각 - 로컬 시각) 초. 실패 시 None."""
    pkt = b"\x1b" + 47 * b"\0"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            t0 = time.time()
            s.sendto(pkt, (server, 123))
            data, _ = s.recvfrom(48)
            t3 = time.time()
    except OSError as e:
        log.warning("NTP 실패(%s): %s", server, e)
        return None

    def ts(b):
        sec, frac = struct.unpack("!II", b)
        return sec - NTP_EPOCH + frac / 2 ** 32

    t1, t2 = ts(data[32:40]), ts(data[40:48])
    return ((t1 - t0) + (t2 - t3)) / 2


def http_offset(url="https://www.auc.or.kr/", samples=5, gap=0.3, timeout=5.0):
    """응답 헤더 Date로 추정한 (서버 시각 - 로컬 시각) 초. 정밀도 약 ±0.5초."""
    vals = []
    for _ in range(samples):
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0"})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                hdr = r.headers.get("Date")
            t1 = time.time()
        except Exception as e:  # noqa: BLE001
            log.warning("서버 시간 조회 실패: %s", e)
            continue
        if hdr:
            server = parsedate_to_datetime(hdr).timestamp() + 0.5
            vals.append(server - (t0 + t1) / 2)
        time.sleep(gap)
    return statistics.median(vals) if vals else None


class Clock:
    """보정된 현재 시각. offset = 기준 시각 - 로컬 시각."""

    def __init__(self):
        self.offset = 0.0
        self.source = "local"
        self.ntp = None

    def sync_ntp(self, server):
        off = ntp_offset(server)
        if off is not None:
            self.ntp = off
            self.offset, self.source = off, "ntp"
            log.info("NTP 오차: 로컬 시계가 %+.3f초 %s", abs(off), "느림" if off > 0 else "빠름")
        return off

    def sync_http(self, url):
        off = http_offset(url)
        if off is None:
            return None
        log.info("사이트 서버 시간 오차(추정): %+.3f초", off)
        # 서버가 NTP와 0.6초 이내로 맞으면 더 정밀한 NTP 값 유지
        if self.ntp is not None and abs(off - self.ntp) <= 0.6:
            log.info("서버 시계가 NTP와 일치 → NTP 기준 사용")
        else:
            self.offset, self.source = off, "server"
            log.warning("서버 시계 기준으로 보정 (offset %+.3f초)", off)
        return off

    def now_ts(self):
        return time.time() + self.offset

    def now(self):
        return datetime.fromtimestamp(self.now_ts(), KST)

    def sleep_until(self, dt):
        target = dt.timestamp()
        while True:
            rem = target - self.now_ts()
            if rem <= 0:
                return
            time.sleep(min(rem - 0.05, 10) if rem > 0.1 else 0.005)
