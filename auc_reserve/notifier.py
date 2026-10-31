"""소리 + 텔레그램 알림. 두 채널은 서로 독립적으로 동작한다."""
import logging
import sys
import threading
import urllib.parse
import urllib.request

log = logging.getLogger("notify")


class Notifier:
    def __init__(self, cfg):
        n = cfg.get("notify", {})
        self.token = n.get("telegram_token", "").strip()
        self.chat_id = str(n.get("chat_id", "")).strip()
        self.sound = n.get("sound", True)

    def info(self, msg):
        """텔레그램만 (소리 없음)."""
        log.info("[알림] %s", msg)
        self._telegram(msg)

    def alert(self, msg):
        """소리 + 텔레그램. 사용자가 PC 앞으로 와야 할 때."""
        log.warning("[호출] %s", msg)
        self._sound()
        self._telegram("🔔 " + msg)

    def _sound(self):
        if not self.sound:
            return

        def run():
            try:
                if sys.platform == "win32":
                    import winsound
                    for _ in range(3):
                        winsound.Beep(1500, 300)
                        winsound.Beep(1000, 300)
                else:
                    print("\a" * 3, end="", flush=True)
            except Exception as e:  # noqa: BLE001
                log.warning("소리 알림 실패: %s", e)

        threading.Thread(target=run, daemon=True).start()

    def _telegram(self, msg):
        if not (self.token and self.chat_id):
            return

        def run():
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": msg}).encode()
                urllib.request.urlopen(url, data=data, timeout=5).read()
            except Exception as e:  # noqa: BLE001
                # 토큰이 로그에 남지 않도록 예외 종류만 기록
                log.warning("텔레그램 전송 실패: %s", type(e).__name__)

        threading.Thread(target=run, daemon=True).start()
