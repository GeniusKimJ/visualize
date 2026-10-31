"""안양도시공사 체육시설 반자동 예약 도우미.

최종 신청 버튼은 사용자가 직접 누른다. 보안문자/본인인증/키보드보안은 우회하지 않는다.

사용법:
  python main.py --login      로그인 대기 (사전 준비)
  python main.py --check      로그인/셀렉터/목표 날짜 점검 (토요일 테스트)
  python main.py --inspect    실제 화면 HTML/요소 저장 (셀렉터 찾기용)
  python main.py --open       일요일 오픈 대기 → 즉시 예약
  python main.py --watch      빈자리 감시
  python main.py --open --dry-run   브라우저 없이 계산/일정만 출력
"""
import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import site_selectors as S
from notifier import Notifier
from schedule import (KST, build_targets, calendar_url, rolling_bookable, rolling_plan,
                      target_week, upcoming_open)
from timesync import Clock

BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "logs"
log = logging.getLogger("main")


# ─────────────────────────── 설정 / 로그 ───────────────────────────
def load_env(path):
    """.env 파일을 os.environ에 로드 (python-dotenv 없이)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("open_mode", "rolling")        # rolling: 이용일 N일 전 오픈 / weekly: 매주 정해진 요일
    cfg.setdefault("open_days_before", 7)
    cfg.setdefault("open_weekday", "SUN")
    cfg.setdefault("open_time", "15:00:00")
    cfg.setdefault("max_per_week", 2)
    cfg.setdefault("watch_on_fail", "ask")       # ask | auto | off
    cfg.setdefault("final_wait_min", 10)
    cfg.setdefault("keepalive_min", 10)
    cfg.setdefault("max_wait_after_open_min", 30)
    cfg.setdefault("ntp_server", "time.google.com")
    cfg.setdefault("browser", {})
    cfg["browser"].setdefault("channel", "chrome")
    cfg["browser"].setdefault("profile_dir", "chrome_profile")
    cfg["keepalive_min"] = max(5, cfg["keepalive_min"])   # 세션 유지 접근은 5분 이상 간격
    return cfg


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
                            "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / f"run_{datetime.now():%Y%m%d}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)


def mask(s):
    return s[:2] + "*" * max(0, len(s) - 2) if s else ""


def fmt_dt(dt):
    return f"{dt:%Y-%m-%d}({'월화수목금토일'[dt.weekday()]}) {dt:%H:%M:%S}"


TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(\s*[~\-–]\s*\d{1,2}:\d{2})?")


def fill_date(template, d):
    return template.format(ymd=d.isoformat(), ymd8=d.strftime("%Y%m%d"), day=d.day, dd=f"{d.day:02d}")


def slot_starts_at(text, hhmm):
    """'19:00~20:00' 같은 범위는 시작 시각만 비교 ('20:00'이 19시 슬롯에 걸리지 않도록)."""
    h, m = hhmm.split(":")
    want = (int(h), int(m))
    return any((int(a), int(b)) == want for a, b, _ in TIME_RE.findall(text))


def make_plan(cfg, now):
    if cfg["open_mode"] == "weekly":
        open_dt = upcoming_open(now, cfg["open_weekday"], cfg["open_time"])
        return open_dt, build_targets(cfg, open_dt)
    return rolling_plan(cfg, now)


def print_plan(open_dt, targets, cfg):
    print("\n" + "=" * 60)
    if open_dt is None:
        print(" 예정된 오픈 없음 (config.json의 target_days / extra_dates 확인)")
        print("=" * 60 + "\n")
        return
    print(f" 오픈 일시 : {fmt_dt(open_dt)}")
    if cfg["open_mode"] == "weekly":
        week = target_week(open_dt)
        print(f" 예약 주간 : {week[0]} ~ {week[-1]}")
    else:
        print(f" 오픈 규칙 : 이용일 {cfg['open_days_before']}일 전 {cfg['open_time'][:5]}")
    print(f" 최대 예약 : {cfg['max_per_week']}건")
    print("-" * 60)
    if not targets:
        print(" (목표 날짜 없음)")
    for i, t in enumerate(targets, 1):
        print(f" {i}. {t.label()}  시간 {t.times}  코트 {t.facilities}  [{t.source}]")
    print("=" * 60 + "\n")


# ─────────────────────────── 브라우저 봇 ───────────────────────────
class Bot:
    def __init__(self, cfg, notifier, clock):
        self.cfg = cfg
        self.n = notifier
        self.clock = clock
        self.phase = "auto"            # auto: 스크립트 진행 / user: 사용자 최종 신청 단계
        self.last_dialog = ""
        self.final_confirm_blocked = False
        self.no_court = False
        self.picked_courts = []
        self.last_access = 0.0
        self.pw = self.ctx = self.page = None

    # ── 시작/종료 ──
    def start(self):
        from playwright.sync_api import sync_playwright
        b = self.cfg["browser"]
        channel = os.environ.get("AUC_BROWSER_CHANNEL", b["channel"]) or None
        self.pw = sync_playwright().start()
        self.ctx = self.pw.chromium.launch_persistent_context(
            user_data_dir=str(BASE / b["profile_dir"]),
            channel=channel,
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
            executable_path=os.environ.get("AUC_BROWSER_PATH") or None,
        )
        self.ctx.set_default_timeout(10_000)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.on("dialog", self._on_dialog)
        self.ctx.on("page", self._on_new_page)

    def stop(self):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self.pw:
                self.pw.stop()

    def _on_dialog(self, d):
        msg = d.message
        self.last_dialog = msg
        log.info("대화상자(%s): %s", d.type, msg)
        if self.phase == "user":
            # 사용자가 직접 누른 최종 버튼에 뒤따르는 확인창
            d.accept()
            return
        if d.type == "confirm" and any(k in msg for k in S.FINAL_CONFIRM_KEYWORDS):
            self.final_confirm_blocked = True
            log.warning("최종 확인창 감지 → 자동 단계에서는 취소하고 사용자에게 넘김")
            d.dismiss()
            return
        d.accept()

    def _on_new_page(self, p):
        log.warning("새 창 열림: %s", p.url)
        self.n.alert("새 창이 열렸습니다(인증 팝업일 수 있음). 브라우저를 확인해주세요.")

    # ── 공통 ──
    def goto(self, url):
        self.page.goto(url, wait_until="domcontentloaded")
        self.last_access = time.monotonic()

    def settle(self, ms=300):
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:  # noqa: BLE001
            pass
        self.page.wait_for_timeout(ms)

    def screenshot(self, name):
        try:
            p = LOG_DIR / f"{name}_{datetime.now():%H%M%S}.png"
            self.page.screenshot(path=str(p), full_page=True)
            log.info("스크린샷 저장: %s", p.name)
        except Exception as e:  # noqa: BLE001
            log.warning("스크린샷 실패: %s", e)

    def count(self, sel):
        try:
            return self.page.locator(sel).count()
        except Exception:  # noqa: BLE001
            return 0

    def body_text(self):
        try:
            return self.page.inner_text("body", timeout=3000)
        except Exception:  # noqa: BLE001
            return ""

    # ── 로그인 ──
    def is_logged_in(self):
        if self.count(S.LOGGED_OUT_MARKER):
            return False
        return self.count(S.LOGGED_IN_MARKER) > 0

    def check_login(self):
        """메인 페이지를 열어 로그인 상태 확인."""
        self.goto(S.MAIN_URL)
        ok = self.is_logged_in()
        log.info("로그인 상태: %s", "유지됨" if ok else "로그아웃")
        return ok

    def ensure_login(self, wait_min=5):
        if self.check_login():
            return True
        self.goto(S.LOGIN_URL)
        uid = os.environ.get("AUC_ID", "")
        if uid and self.count(S.LOGIN_ID_INPUT):
            self.page.locator(S.LOGIN_ID_INPUT).first.fill(uid)
            log.info("아이디 자동 입력: %s", mask(uid))
        self.n.alert("로그인이 필요합니다. 브라우저에서 비밀번호를 입력하고 로그인해주세요.")
        deadline = time.monotonic() + wait_min * 60
        while time.monotonic() < deadline:
            if self.is_logged_in():
                log.info("로그인 확인")
                self.last_access = time.monotonic()
                return True
            time.sleep(1)
        self.n.alert(f"{wait_min}분 안에 로그인이 확인되지 않았습니다.")
        return False

    # ── 우회하지 않는 단계 감지 ──
    def find_blocker(self):
        for name, sel in S.BLOCKER_SELECTORS.items():
            if self.count(sel):
                return name
        text = self.body_text()
        for name, words in S.BLOCKER_TEXTS.items():
            if any(w in text for w in words):
                return name
        return None

    def handle_blockers(self, wait_min=10):
        name = self.find_blocker()
        if not name:
            return True
        self.n.alert(f"{name} 단계가 나왔습니다. 브라우저에서 직접 처리해주세요.")
        deadline = time.monotonic() + wait_min * 60
        while time.monotonic() < deadline:
            time.sleep(2)
            if not self.find_blocker():
                log.info("%s 처리 완료 → 계속 진행", name)
                return True
        self.n.alert(f"{name} 단계가 {wait_min}분 동안 처리되지 않았습니다.")
        return False

    # ── 달력 / 슬롯 ──
    def date_cell(self, d):
        return fill_date(S.DATE_CELL, d)

    def goto_calendar(self, d):
        self.goto(calendar_url(d, S.CALENDAR_FIRST_OF_MONTH))

    def date_is_open(self, d):
        cell = self.page.locator(self.date_cell(d))
        if cell.count() == 0:
            return False
        try:
            txt = cell.first.inner_text(timeout=2000)
        except Exception:  # noqa: BLE001
            txt = ""
        return not any(k in txt for k in S.NOT_OPEN_TEXTS)

    def open_date(self, d):
        self.goto_calendar(d)
        if S.DATE_CELL_CLICK:
            cell = self.page.locator(self.date_cell(d))
            if cell.count():
                cell.first.click()
                self.settle()
            else:
                log.warning("%s 날짜 칸을 찾지 못함 (DATE_CELL 확인 필요)", d)

    def find_slot(self, d, times, facilities):
        items = self.page.locator(fill_date(S.SLOT_ITEM, d))
        rows = []
        for i in range(items.count()):
            try:
                rows.append((i, " ".join(items.nth(i).inner_text(timeout=2000).split())))
            except Exception:  # noqa: BLE001
                continue
        for t in times:
            for f in (facilities or [""]):      # 코트 구분이 없는 시설은 facilities를 비워 둠
                for i, txt in rows:
                    if slot_starts_at(txt, t) and f in txt:
                        row = items.nth(i)
                        btn = row.locator(S.SLOT_CLICK)
                        if any(u in txt for u in S.UNAVAILABLE_TEXTS) or (
                                S.SLOT_CLICK_REQUIRED and not btn.count()):
                            log.info("마감: %s %s", t, f)
                            continue
                        return t, f, (btn.first if btn.count() else row)
        return None

    # ── 신청서 → 최종 직전 ──
    def fill_applicant(self):
        for key, sel in S.APPLICANT_FIELDS.items():
            val = self.cfg.get("applicant", {}).get(key)
            if val in (None, "") or not self.count(sel):
                continue
            el = self.page.locator(sel).first
            try:
                tag = el.evaluate("e => e.tagName").lower()
                if tag == "select":
                    try:
                        el.select_option(label=str(val))
                    except Exception:  # noqa: BLE001
                        el.select_option(value=str(val))
                else:
                    el.fill(str(val))
                log.info("신청서 입력: %s", key)
                if S.AFTER_FILL_JS:
                    self.page.evaluate(S.AFTER_FILL_JS)
            except Exception as e:  # noqa: BLE001
                log.warning("신청서 입력 실패(%s): %s", key, e)

    def select_courts(self):
        """코트 선택 화면이면 config의 courts 우선순위대로 체크. 반환: 선택한 코트 번호 목록 (화면이 아니면 None)."""
        boxes = self.page.locator(S.COURT_CHECKBOX)
        if not boxes.count():
            return None
        # 예약된/점검 코트: disabled 이거나 라벨에 색 배경(빨강/주황/초록)이 칠해진 경우
        info = boxes.evaluate_all("""els => els.map(e => {
            const lb = e.id ? document.querySelector('label[for="' + e.id + '"]') : null;
            const st = ((lb && lb.getAttribute('style')) || '') + (e.getAttribute('style') || '');
            const bg = lb ? getComputedStyle(lb).backgroundColor : '';
            const colored = /background/i.test(st) || ['rgb(255, 0, 0)', 'rgb(255, 165, 0)', 'rgb(0, 128, 0)'].includes(bg);
            return {no: parseInt(e.value), ok: !e.disabled && !colored, checked: e.checked};
        })""")
        free = [c["no"] for c in info if c["ok"]]
        want = int(self.cfg.get("court_count", 1))
        want = max(1, min(want, S.COURT_MAX))
        order = [n for n in self.cfg.get("courts", []) if n in free]
        if self.cfg.get("court_fallback_any", True):
            order += [n for n in free if n not in order]
        pick = order[:want]
        log.info("빈 코트 %s → 선택 %s", free, pick)
        for c in info:
            if c["checked"] and c["no"] not in pick:
                self.page.locator(f'{S.COURT_CHECKBOX}[value="{c["no"]}"]').uncheck()
        for n in pick:
            self.page.locator(f'{S.COURT_CHECKBOX}[value="{n}"]').check()
        return pick

    def check_agreements(self):
        boxes = self.page.locator(S.AGREE_CHECKBOXES)
        for i in range(boxes.count()):
            try:
                if boxes.nth(i).is_visible() and not boxes.nth(i).is_checked():
                    boxes.nth(i).check()
            except Exception:  # noqa: BLE001
                pass

    def final_visible(self):
        loc = self.page.locator(S.FINAL_SUBMIT)
        for i in range(loc.count()):
            try:
                if loc.nth(i).is_visible():
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def proceed_to_final(self, max_steps=6):
        """중간 단계를 진행하고 최종 신청 직전에서 멈춘다. 최종 버튼은 누르지 않는다."""
        for _ in range(max_steps):
            if not self.handle_blockers():
                return False
            picked = self.select_courts()
            if picked is not None:
                if not picked:
                    log.info("선택 가능한 코트 없음")
                    self.no_court = True
                    return False
                self.picked_courts = picked
            self.fill_applicant()
            self.check_agreements()
            if self.final_confirm_blocked or self.final_visible():
                return True
            clicked = False
            for sel in S.FLOW_NEXT_BUTTONS:
                loc = self.page.locator(sel)
                if not loc.count() or not loc.first.is_visible():
                    continue
                label = loc.first.inner_text().strip()
                if any(k in label for k in S.FINAL_BUTTON_TEXTS):
                    log.info("'%s'는 최종 버튼으로 판단 → 누르지 않음", label)
                    return True
                log.info("다음 단계: '%s'", label)
                loc.first.click()
                self.settle()
                clicked = True
                break
            if not clicked:
                return False
        return self.final_visible()

    def wait_user_complete(self, minutes):
        self.phase = "user"
        deadline = time.monotonic() + minutes * 60
        try:
            while time.monotonic() < deadline:
                if any(k in self.last_dialog for k in S.COMPLETE_TEXTS):
                    return True
                if any(p in self.page.url for p in S.COMPLETE_URL_PARTS):
                    return True
                if any(k in self.body_text() for k in S.COMPLETE_TEXTS):
                    return True
                time.sleep(1)
            return False
        finally:
            self.phase = "auto"

    def try_book(self, tg):
        """반환: (상태, 설명). 상태 = 성공 | 마감 | 미완료 | 실패"""
        self.final_confirm_blocked = False
        self.last_dialog = ""
        self.no_court = False
        self.picked_courts = []
        try:
            self.open_date(tg.day)
            if not self.handle_blockers():
                return "실패", "인증/대기 단계 미처리"
            slot = self.find_slot(tg.day, tg.times, tg.facilities)
            if not slot:
                return "마감", "원하는 시간/코트 없음"
            t, f, el = slot
            label = f"{tg.label()} {t} {f}".strip()
            log.info("슬롯 선택: %s", label)
            el.click()
            self.settle()
            if any(k in self.last_dialog for k in S.UNAVAILABLE_DIALOG_TEXTS):
                return "마감", self.last_dialog
            ok = self.proceed_to_final()
            if self.no_court:
                return "마감", label + " (빈 코트 없음)"
            if self.picked_courts:
                label += " 코트 " + ",".join(f"{n}번" for n in self.picked_courts)
            if ok:
                self.n.alert(f"{label}, [예약하기] → [예]를 눌러주세요")
            else:
                self.screenshot("flow_stuck")
                self.n.alert(f"{label}, 신청 화면을 끝까지 자동 진행하지 못했습니다. 직접 진행해주세요")
            if self.wait_user_complete(self.cfg["final_wait_min"]):
                return "성공", label
            return "미완료", label + f" ({self.cfg['final_wait_min']}분 내 완료 미확인)"
        except Exception as e:  # noqa: BLE001
            log.exception("예약 중 오류")
            self.screenshot("error")
            return "실패", f"{type(e).__name__}: {e}"


# ─────────────────────────── 실행 모드 ───────────────────────────
def confirm(question, default=True):
    ans = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not ans else ans.startswith("y")


def book_all(bot, targets, cfg):
    results, booked = [], 0
    for tg in targets:
        if booked >= cfg["max_per_week"]:
            results.append((tg, "건너뜀", "주간 최대 건수 도달"))
            continue
        status, detail = bot.try_book(tg)
        log.info("결과 %s: %s %s", tg.label(), status, detail)
        results.append((tg, status, detail))
        if status == "성공":
            booked += 1
    return results, booked


def report(results, notifier):
    lines = ["[예약 결과]"] + [f"{tg.label()}  {st}  {de}" for tg, st, de in results]
    text = "\n".join(lines)
    print("\n" + text + "\n")
    notifier.info(text)


def wait_until_open(bot, clock, cfg, open_dt, first_day):
    """오픈 전 점검 일정 → 오픈 2초 전부터 1초 간격 확인. 열렸으면 True."""
    events = [
        (open_dt - timedelta(minutes=30), "login"),
        (open_dt - timedelta(minutes=10), "login"),
        (open_dt - timedelta(minutes=5), "http_sync"),
        (open_dt - timedelta(minutes=3), "prepare"),
    ]
    keep = cfg["keepalive_min"] * 60
    for when, act in events:
        if when <= clock.now():
            continue
        while True:
            next_keep = clock.now() + timedelta(seconds=keep - (time.monotonic() - bot.last_access))
            if next_keep >= when:
                break
            clock.sleep_until(next_keep)
            log.info("세션 유지 점검")
            if not bot.check_login():
                bot.ensure_login()
        clock.sleep_until(when)
        log.info("점검 시각 도달: %s", act)
        if act == "login":
            if not bot.check_login():
                bot.ensure_login()
        elif act == "http_sync":
            clock.sync_ntp(cfg["ntp_server"])
            clock.sync_http(S.SERVER_TIME_URL)
        elif act == "prepare":
            if not bot.check_login():
                bot.ensure_login(wait_min=2)
            bot.goto_calendar(first_day)

    clock.sleep_until(open_dt - timedelta(seconds=2))
    log.info("오픈 확인 시작 (기준 시계: %s, offset %+.3f초)", clock.source, clock.offset)
    interval, slowed = 1.0, False
    while True:
        t0 = time.monotonic()
        try:
            bot.goto_calendar(first_day)
            bot.handle_blockers()
            if bot.date_is_open(first_day):
                log.info("★ 예약 오픈 확인 (%s)", clock.now().strftime("%H:%M:%S.%f")[:-3])
                return True
        except Exception as e:  # noqa: BLE001
            log.warning("오픈 확인 중 오류: %s", e)
        elapsed = (clock.now() - open_dt).total_seconds()
        if elapsed > 180 and not slowed:
            interval, slowed = 5.0, True
            bot.n.alert("오픈 3분이 지나도 열리지 않습니다. 오픈 시각 설정이나 DATE_CELL 셀렉터를 확인해주세요.")
        if elapsed > cfg["max_wait_after_open_min"] * 60:
            bot.n.alert("오픈 대기 시간을 초과해 중단합니다.")
            return False
        time.sleep(max(0.0, interval - (time.monotonic() - t0)))


def run_watch(bot, targets, cfg, already_booked=0):
    log.info("빈자리 감시 시작 (최소 30초 + 랜덤 0~15초 간격)")
    pending, booked = list(targets), already_booked
    while pending and booked < cfg["max_per_week"]:
        today = datetime.now(KST).date()
        pending = [t for t in pending if t.day >= today]
        for tg in list(pending):
            if not bot.is_logged_in() and not bot.check_login():
                bot.ensure_login()
            bot.open_date(tg.day)
            bot.handle_blockers()
            if bot.find_slot(tg.day, tg.times, tg.facilities):
                bot.n.alert(f"빈자리 발견: {tg.label()}")
                status, detail = bot.try_book(tg)
                log.info("감시 결과 %s: %s %s", tg.label(), status, detail)
                if status == "성공":
                    booked += 1
                    pending.remove(tg)
            time.sleep(random.uniform(1, 3))
        time.sleep(30 + random.uniform(0, 15))
    bot.n.info("빈자리 감시 종료")


def cmd_inspect(bot, first_day):
    bot.goto_calendar(first_day)
    js = """() => [...document.querySelectorAll('a,button,input,select,td[onclick],li[onclick],div[onclick]')]
      .filter(e => e.offsetParent !== null).slice(0, 800).map(e => ({
        tag: e.tagName.toLowerCase(), id: e.id, name: e.getAttribute('name'),
        cls: e.className && String(e.className), type: e.getAttribute('type'),
        href: e.getAttribute('href'), onclick: e.getAttribute('onclick'),
        data: Object.assign({}, e.dataset), text: (e.innerText || e.value || '').trim().slice(0, 60)}))"""
    print("\n브라우저에서 원하는 화면(로그인, 달력, 시간표, 신청서 등)으로 이동한 뒤 Enter를 누르면 저장합니다.")
    n = 0
    while True:
        ans = input("저장: Enter / 종료: q > ").strip().lower()
        if ans == "q":
            break
        n += 1
        stem = LOG_DIR / f"inspect_{datetime.now():%H%M%S}_{n}"
        stem.with_suffix(".html").write_text(bot.page.content(), encoding="utf-8")
        elems = bot.page.evaluate(js)
        stem.with_suffix(".json").write_text(json.dumps({"url": bot.page.url, "elements": elems},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
        bot.page.screenshot(path=str(stem.with_suffix(".png")), full_page=True)
        print(f"  저장됨: {stem.name}.html / .json / .png  ({bot.page.url})")


def cmd_check(bot, clock, cfg, targets):
    clock.sync_ntp(cfg["ntp_server"])
    clock.sync_http(S.SERVER_TIME_URL)
    logged = bot.check_login()
    rows = [("로그인 상태(LOGGED_IN_MARKER)", "유지됨" if logged else "로그아웃")]
    if targets:
        d = targets[0].day
        bot.goto_calendar(d)
        rows.append((f"날짜 칸 DATE_CELL ({d})", bot.count(bot.date_cell(d))))
        rows.append(("오픈 여부 판정", bot.date_is_open(d)))
        if S.DATE_CELL_CLICK and bot.count(bot.date_cell(d)):
            bot.page.locator(bot.date_cell(d)).first.click()
            bot.settle()
        n = bot.count(fill_date(S.SLOT_ITEM, d))
        rows.append(("시간표 SLOT_ITEM", n))
        items = bot.page.locator(fill_date(S.SLOT_ITEM, d))
        for i in range(min(n, 8)):
            try:
                rows.append((f"  행 {i + 1}", " ".join(items.nth(i).inner_text().split())[:70]))
            except Exception:  # noqa: BLE001
                pass
        slot = bot.find_slot(d, targets[0].times, targets[0].facilities)
        rows.append(("목표 시간 예약가능", f"{slot[0]} {slot[1]}".strip() if slot else "없음"))
        rows.append(("인증/대기 감지", bot.find_blocker() or "없음"))
    print("\n[점검 결과]")
    for k, v in rows:
        print(f"  {k:<32} {v}")
    print("\n값이 0이거나 이상하면 --inspect로 화면을 저장해 site_selectors.py를 수정하세요.")


def dry_run(open_dt, cfg):
    print("[dry-run] 예정된 동작 (브라우저 실행 안 함)")
    plan = [
        (open_dt - timedelta(minutes=40), "스크립트 시작, 로그인 확인 (필요 시 알림)"),
        (open_dt - timedelta(minutes=30), "로그인 점검"),
        (open_dt - timedelta(minutes=10), "로그인 점검"),
        (open_dt - timedelta(minutes=5), "NTP + 서버 시간 보정"),
        (open_dt - timedelta(minutes=3), "로그인 점검 + 첫 목표 날짜 달력 열기"),
        (open_dt - timedelta(seconds=2), "1초 간격 새로고침으로 오픈 확인 시작"),
        (open_dt + timedelta(minutes=3), "아직 안 열렸으면 5초 간격 + 알림"),
        (open_dt + timedelta(minutes=cfg["max_wait_after_open_min"]), "대기 중단"),
    ]
    for when, what in plan:
        print(f"  {fmt_dt(when)}  {what}")
    print(f"  세션 유지 점검: {cfg['keepalive_min']}분 간격 / 최종 신청 대기: {cfg['final_wait_min']}분")


def main():
    ap = argparse.ArgumentParser(description="안양도시공사 체육시설 반자동 예약 도우미")
    g = ap.add_mutually_exclusive_group(required=True)
    for m in ("login", "check", "inspect", "open", "watch"):
        g.add_argument(f"--{m}", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="브라우저 없이 계산/일정만 출력")
    ap.add_argument("--yes", action="store_true", help="목표 확인 질문 생략 (작업 스케줄러용)")
    ap.add_argument("--config", default=str(BASE / "config.json"))
    args = ap.parse_args()

    setup_logging()
    load_env(BASE / ".env")
    cfg = load_config(Path(args.config))
    notifier = Notifier(cfg)
    clock = Clock()

    now = datetime.now(KST)
    open_dt, targets = make_plan(cfg, now)
    if args.watch and cfg["open_mode"] == "rolling":
        targets = rolling_bookable(cfg, now)
        print("[감시 대상] 이미 열려 있는 목표 날짜: " + (", ".join(t.label() for t in targets) or "없음"))
    else:
        print_plan(open_dt, targets, cfg)

    if args.dry_run:
        if args.open and open_dt:
            dry_run(open_dt, cfg)
        return

    if args.open or args.watch:
        if not targets:
            log.error("목표 날짜가 없습니다. config.json을 확인하세요.")
            return
        if args.open and args.yes and open_dt - now > timedelta(hours=2):
            # 작업 스케줄러가 매일 실행할 때: 오늘 열리는 목표가 없으면 바로 종료
            log.info("오늘 열리는 목표 날짜 없음 (다음 오픈 %s) → 종료", fmt_dt(open_dt))
            return
        if not args.yes and not confirm("위 내용으로 진행할까요?"):
            return
        notifier.info("예약 도우미 시작\n" + "\n".join(
            f"{t.label()} {t.times} {t.facilities}" for t in targets))

    bot = Bot(cfg, notifier, clock)
    error = False
    try:
        bot.start()
        if args.login:
            bot.ensure_login()
        elif args.check:
            cmd_check(bot, clock, cfg, targets)
        elif args.inspect:
            cmd_inspect(bot, (targets[0].day if targets else datetime.now(KST).date()))
        elif args.watch:
            bot.ensure_login()
            run_watch(bot, targets, cfg)
        elif args.open:
            clock.sync_ntp(cfg["ntp_server"])
            bot.ensure_login(wait_min=15)
            opened = True
            if clock.now() < open_dt:
                opened = wait_until_open(bot, clock, cfg, open_dt, targets[0].day)
            results, booked = book_all(bot, targets, cfg) if opened else ([], 0)
            if results:
                report(results, notifier)
            if booked < cfg["max_per_week"]:
                mode = cfg["watch_on_fail"]
                left = [tg for tg, st, _ in results if st != "성공"] or targets
                if mode == "auto" or (mode == "ask" and confirm("빈자리 감시 모드로 전환할까요?")):
                    run_watch(bot, left, cfg, booked)
    except KeyboardInterrupt:
        log.info("사용자 중단")
    except Exception:  # noqa: BLE001
        error = True
        log.exception("오류 발생")
        if bot.page:
            bot.screenshot("fatal")
        notifier.alert("스크립트 오류가 발생했습니다. 브라우저에서 직접 이어서 진행해주세요.")
    finally:
        if bot.ctx:
            msg = "오류가 있었습니다. 브라우저 화면은 그대로 둡니다." if error else "작업 끝."
            try:
                input(f"\n{msg} Enter를 누르면 브라우저를 닫고 종료합니다... ")
            except (EOFError, KeyboardInterrupt):
                pass
        bot.stop()


if __name__ == "__main__":
    main()
