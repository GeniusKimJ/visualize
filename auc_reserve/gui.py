"""안양도시공사 배드민턴장 예약 도우미 — 창(GUI) 버전.

실행: python gui.py            (창 열기)
      python gui.py --auto     (창을 열고 바로 오픈 대기 시작 — 작업 스케줄러용)
      python gui.py --open ... (그 밖의 인자는 명령행 버전(main.py)으로 그대로 전달)
"""
import json
import logging
import os
import queue
import re
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

import main as core
from schedule import KST, WEEKDAY_KO

WEEKDAY_KEYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FONT = ("맑은 고딕", 10)


def parse_times(text):
    """'18:50, 20:30' → ['18:50', '20:30'] (형식이 틀리면 ValueError)."""
    items = [x.strip() for x in re.split(r"[,\s]+", text) if x.strip()]
    for x in items:
        if not TIME_RE.match(x):
            raise ValueError(f"시간 형식이 아닙니다: {x} (예: 18:50)")
    return items


class QueueLogHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.q.put(("log", self.format(record), record.levelno))


class App:
    def __init__(self, root, auto=False):
        self.root = root
        self.auto = auto
        self.q = queue.Queue()
        self.worker = None
        self.close_event = threading.Event()
        self.browser_open = False
        self.cfg_path = core.BASE / "config.json"
        self.env_path = core.BASE / ".env"

        root.title("배드민턴장 예약 도우미 (안양도시공사 호계체육관)")
        root.geometry("900x800")
        root.minsize(820, 640)
        style = ttk.Style()
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
        style.configure(".", font=FONT)
        style.configure("Status.TLabel", font=("맑은 고딕", 11, "bold"), foreground="#1f4e9c")
        style.configure("Big.TButton", font=("맑은 고딕", 10, "bold"))

        self.cfg = self.load_cfg()
        self.build()
        self.fill_from_cfg()

        core.setup_logging()
        logging.getLogger().addHandler(QueueLogHandler(self.q))

        self.refresh_plan()
        self.root.after(100, self.pump)
        self.root.after(1000, self.tick)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        if auto:
            self.root.after(1500, lambda: self.start(["--open", "--yes"], ask=False))

    # ───────────────────────── 화면 구성 ─────────────────────────
    def build(self):
        top = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        self.plan_var = tk.StringVar(value="")
        self.count_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.plan_var, style="Status.TLabel").pack(anchor="w")
        ttk.Label(top, textvariable=self.count_var).pack(anchor="w")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="x", padx=12, pady=4)
        nb.add(self.build_main_tab(nb), text="  예약 설정  ")
        nb.add(self.build_adv_tab(nb), text="  고급 설정  ")

        bar1 = ttk.Frame(self.root, padding=(12, 6, 12, 2))
        bar1.pack(fill="x")
        bar2 = ttk.Frame(self.root, padding=(12, 2, 12, 6))
        bar2.pack(fill="x")
        self.btns = {}
        for bar, key, text, cmd, style in [
            (bar1, "save", "설정 저장", self.save_cfg, None),
            (bar1, "plan", "일정 확인", lambda: self.start(["--open", "--dry-run"], ask=False), None),
            (bar1, "check", "점검", lambda: self.start(["--check"], ask=False), None),
            (bar1, "login", "로그인 테스트", lambda: self.start(["--login"], ask=False), None),
            (bar2, "open", "▶  오픈 대기 시작", lambda: self.start(["--open", "--yes"]), "Big.TButton"),
            (bar2, "watch", "빈자리 감시", lambda: self.start(["--watch", "--yes"]), None),
            (bar2, "stop", "■  중지", self.stop, None),
            (bar2, "close", "브라우저 닫기", self.close_browser, None),
        ]:
            b = ttk.Button(bar, text=text, command=cmd, style=style) if style else \
                ttk.Button(bar, text=text, command=cmd)
            b.pack(side="left", padx=3)
            self.btns[key] = b
        self.set_running(False)

        logf = ttk.LabelFrame(self.root, text=" 진행 기록 ", padding=6)
        logf.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.logbox = scrolledtext.ScrolledText(logf, height=14, font=("맑은 고딕", 9), state="disabled")
        self.logbox.pack(fill="both", expand=True)
        self.logbox.tag_config("warn", foreground="#c0392b")
        self.logbox.tag_config("ok", foreground="#1e8449")

    def build_main_tab(self, parent):
        f = ttk.Frame(parent, padding=10)

        days = ttk.LabelFrame(f, text=" 매주 예약할 요일과 시간 (앞쪽 시간이 우선) ", padding=8)
        days.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        self.day_on, self.day_times = {}, {}
        for i, wd in enumerate(WEEKDAY_KEYS):
            self.day_on[wd] = tk.BooleanVar()
            self.day_times[wd] = tk.StringVar()
            ttk.Checkbutton(days, text=WEEKDAY_KO[i] + "요일", variable=self.day_on[wd]).grid(
                row=i, column=0, sticky="w", pady=2)
            ttk.Entry(days, textvariable=self.day_times[wd], width=22).grid(row=i, column=1, padx=6)
        ttk.Label(days, text="예) 18:50, 20:30   (평일 09:00 10:40 12:20 13:55 15:30 17:10 18:50 20:30\n"
                             "      일요일 09:00 10:30 12:00 13:30 15:00 16:30)",
                  foreground="#666", font=("맑은 고딕", 8)).grid(row=7, column=0, columnspan=2, sticky="w",
                                                              pady=(6, 0))

        ex = ttk.LabelFrame(f, text=" 특정 날짜 (한 줄에 하나: 날짜 시간,시간) ", padding=8)
        ex.grid(row=0, column=1, sticky="nsew")
        self.extra_box = tk.Text(ex, height=4, width=34, font=FONT)
        self.extra_box.pack(fill="both", expand=True)
        ttk.Label(ex, text="예) 2026-11-14 10:40, 12:20", foreground="#666",
                  font=("맑은 고딕", 8)).pack(anchor="w")
        row = ttk.Frame(ex)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="건너뛸 날짜").pack(side="left")
        self.skip_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.skip_var, width=26).pack(side="left", padx=6)

        ct = ttk.LabelFrame(f, text=" 코트 / 인원 / 제출 ", padding=8)
        ct.grid(row=1, column=1, sticky="nsew", pady=(8, 0))
        self.courts_var = tk.StringVar()
        self.court_count = tk.StringVar(value="2")
        self.people = tk.StringVar(value="4")
        self.fallback = tk.BooleanVar(value=True)
        self.auto_submit = tk.BooleanVar(value=True)
        self.max_per = tk.StringVar(value="1")
        ttk.Label(ct, text="원하는 코트").grid(row=0, column=0, sticky="w")
        ttk.Entry(ct, textvariable=self.courts_var, width=12).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(ct, text="빈칸 = 연번 자동, 예) 6,7", foreground="#666",
                  font=("맑은 고딕", 8)).grid(row=0, column=2, sticky="w")
        ttk.Label(ct, text="코트 수").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(ct, textvariable=self.court_count, values=["1", "2"], width=4, state="readonly").grid(
            row=1, column=1, sticky="w", padx=4)
        ttk.Label(ct, text="사용인원").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(ct, textvariable=self.people, from_=2, to=12, width=5).grid(row=2, column=1, sticky="w",
                                                                              padx=4)
        ttk.Label(ct, text="코트 수×2 ~ ×6명", foreground="#666", font=("맑은 고딕", 8)).grid(
            row=2, column=2, sticky="w")
        ttk.Label(ct, text="최대 예약 건수").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(ct, textvariable=self.max_per, from_=1, to=2, width=5).grid(row=3, column=1, sticky="w",
                                                                              padx=4)
        ttk.Checkbutton(ct, text="지정 코트가 없으면 가까운 빈 코트로", variable=self.fallback).grid(
            row=4, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(ct, text="[예약하기] → [예]까지 자동 (끄면 직전에서 멈춤)", variable=self.auto_submit).grid(
            row=5, column=0, columnspan=3, sticky="w")

        f.columnconfigure(1, weight=1)
        return f

    def build_adv_tab(self, parent):
        f = ttk.Frame(parent, padding=10)
        self.adv = {}
        rows = [
            ("open_time", "오픈 시각", "15:00:00"),
            ("open_days_before", "이용일 며칠 전 오픈", "7"),
            ("open_window_min", "집중 감시 범위(±분)", "1"),
            ("poll_interval_sec", "감시 간격(초, 최소 0.3)", "1.0"),
            ("fast_poll_interval_sec", "오픈 ±20초 간격(초)", "0.5"),
            ("telegram_token", "텔레그램 봇 토큰", ""),
            ("chat_id", "텔레그램 chat_id", ""),
            ("auc_id", "사이트 아이디 (자동 입력용)", ""),
        ]
        for i, (key, label, default) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default)
            ttk.Entry(f, textvariable=v, width=42, show="*" if key == "telegram_token" else "").grid(
                row=i, column=1, sticky="w", padx=8)
            self.adv[key] = v
        self.sound = tk.BooleanVar(value=True)
        self.block_images = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="알림 소리", variable=self.sound).grid(row=len(rows), column=0, sticky="w")
        ttk.Checkbutton(f, text="이미지 차단 (화면 이동 빠르게)", variable=self.block_images).grid(
            row=len(rows), column=1, sticky="w", padx=8)
        ttk.Label(f, text="비밀번호는 키보드보안 때문에 저장하지 않습니다. 로그인 창이 뜨면 직접 입력하세요.",
                  foreground="#666", font=("맑은 고딕", 8)).grid(row=len(rows) + 1, column=0, columnspan=2,
                                                              sticky="w", pady=(8, 0))
        return f

    # ───────────────────────── 설정 읽기/쓰기 ─────────────────────────
    def load_cfg(self):
        try:
            return json.loads(self.cfg_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("설정 파일 오류", f"config.json을 읽지 못했습니다.\n{e}")
            return {}

    def fill_from_cfg(self):
        c = self.cfg
        days = {td["weekday"].upper(): td for td in c.get("target_days", [])}
        for wd in WEEKDAY_KEYS:
            self.day_on[wd].set(wd in days)
            self.day_times[wd].set(", ".join(days.get(wd, {}).get("times", [])))
        lines = []
        for ex in c.get("extra_dates", []):
            if isinstance(ex, str):
                lines.append(ex)
            else:
                lines.append(f'{ex["date"]} {", ".join(ex.get("times", []))}'.strip())
        self.extra_box.delete("1.0", "end")
        self.extra_box.insert("1.0", "\n".join(lines))
        self.skip_var.set(", ".join(c.get("skip_dates", [])))
        self.courts_var.set(",".join(str(x) for x in c.get("courts", [])))
        self.court_count.set(str(c.get("court_count", 2)))
        self.people.set(str(c.get("applicant", {}).get("사용인원", 4)))
        self.fallback.set(bool(c.get("court_fallback_any", True)))
        self.auto_submit.set(bool(c.get("auto_submit", True)))
        self.max_per.set(str(c.get("max_per_week", 1)))
        for key in ("open_time", "open_days_before", "open_window_min", "poll_interval_sec",
                    "fast_poll_interval_sec"):
            if key in c:
                self.adv[key].set(str(c[key]))
        n = c.get("notify", {})
        self.adv["telegram_token"].set(n.get("telegram_token", ""))
        self.adv["chat_id"].set(str(n.get("chat_id", "")))
        self.sound.set(bool(n.get("sound", True)))
        self.block_images.set(bool(c.get("block_images", True)))
        self.adv["auc_id"].set(self.read_env_id())

    def collect(self):
        """화면 값 → config dict. 형식이 틀리면 ValueError."""
        c = dict(self.cfg)
        c["open_mode"] = c.get("open_mode", "rolling")
        c["target_days"] = []
        for i, wd in enumerate(WEEKDAY_KEYS):
            if self.day_on[wd].get():
                times = parse_times(self.day_times[wd].get())
                if not times:
                    raise ValueError(f"{WEEKDAY_KO[i]}요일 시간을 입력하세요.")
                c["target_days"].append({"weekday": wd, "times": times, "facilities": []})
        extras = []
        for line in self.extra_box.get("1.0", "end").splitlines():
            line = line.strip()
            if not line:
                continue
            date_s, _, rest = line.partition(" ")
            if not DATE_RE.match(date_s):
                raise ValueError(f"날짜 형식이 아닙니다: {date_s} (예: 2026-11-14)")
            datetime.strptime(date_s, "%Y-%m-%d")
            times = parse_times(rest)
            extras.append({"date": date_s, "times": times} if times else date_s)
        c["extra_dates"] = extras
        skips = [x.strip() for x in self.skip_var.get().split(",") if x.strip()]
        for x in skips:
            datetime.strptime(x, "%Y-%m-%d")
        c["skip_dates"] = skips
        courts = [x.strip() for x in self.courts_var.get().split(",") if x.strip()]
        if any(not x.isdigit() or not 1 <= int(x) <= 12 for x in courts):
            raise ValueError("코트 번호는 1~12 숫자를 쉼표로 구분해 입력하세요. 예) 6,7")
        c["courts"] = [int(x) for x in courts]
        cnt = int(self.court_count.get())
        people = int(self.people.get())
        if not cnt * 2 <= people <= cnt * 6:
            raise ValueError(f"코트 {cnt}면의 사용인원은 {cnt * 2}~{cnt * 6}명입니다.")
        c["court_count"] = cnt
        c.setdefault("applicant", {})["사용인원"] = people
        c["court_fallback_any"] = self.fallback.get()
        c["auto_submit"] = self.auto_submit.get()
        c["max_per_week"] = int(self.max_per.get())
        if not TIME_RE.match(self.adv["open_time"].get()[:5]):
            raise ValueError("오픈 시각 형식: 15:00:00")
        c["open_time"] = self.adv["open_time"].get().strip()
        c["open_days_before"] = int(self.adv["open_days_before"].get())
        c["open_window_min"] = float(self.adv["open_window_min"].get())
        c["poll_interval_sec"] = max(0.3, float(self.adv["poll_interval_sec"].get()))
        c["fast_poll_interval_sec"] = max(0.3, float(self.adv["fast_poll_interval_sec"].get()))
        c["notify"] = {"telegram_token": self.adv["telegram_token"].get().strip(),
                       "chat_id": self.adv["chat_id"].get().strip(), "sound": self.sound.get()}
        c["block_images"] = self.block_images.get()
        return c

    def save_cfg(self, quiet=False):
        try:
            c = self.collect()
        except ValueError as e:
            messagebox.showwarning("입력 확인", str(e))
            return False
        self.cfg_path.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_env_id(self.adv["auc_id"].get().strip())
        self.cfg = c
        self.refresh_plan()
        if not quiet:
            self.append("설정을 저장했습니다.", logging.INFO, "ok")
        return True

    def read_env_id(self):
        if not self.env_path.exists():
            return ""
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("AUC_ID="):
                return line.split("=", 1)[1].strip()
        return ""

    def write_env_id(self, uid):
        lines = []
        if self.env_path.exists():
            lines = [x for x in self.env_path.read_text(encoding="utf-8").splitlines()
                     if not x.strip().startswith("AUC_ID=")]
        if uid:
            lines.append(f"AUC_ID={uid}")
        self.env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if uid:
            os.environ["AUC_ID"] = uid

    # ───────────────────────── 다음 오픈 표시 ─────────────────────────
    def refresh_plan(self):
        try:
            cfg = core.load_config(self.cfg_path) if self.cfg_path.exists() else None
        except Exception:  # noqa: BLE001
            cfg = None
        self.open_dt, self.targets = (None, [])
        if cfg:
            self.open_dt, self.targets = core.make_plan(cfg, datetime.now(KST))
        if not self.open_dt:
            self.plan_var.set("예정된 오픈 없음 — 요일 또는 특정 날짜를 설정하고 [설정 저장]을 누르세요")
            return
        tg = ", ".join(f"{t.label()} {'/'.join(t.times)}" for t in self.targets)
        self.plan_var.set(f"다음 오픈  {core.fmt_dt(self.open_dt)}   →   {tg}")
        self.tick(once=True)

    def tick(self, once=False):
        if getattr(self, "open_dt", None):
            left = (self.open_dt - datetime.now(KST)).total_seconds()
            if left > 0:
                d, r = divmod(int(left), 86400)
                h, r = divmod(r, 3600)
                m, sec = divmod(r, 60)
                self.count_var.set(f"남은 시간  {d}일 {h:02d}:{m:02d}:{sec:02d}" if d else
                                   f"남은 시간  {h:02d}:{m:02d}:{sec:02d}")
            else:
                self.count_var.set("오픈 시각이 지났습니다")
        if not once:
            self.root.after(1000, self.tick)

    # ───────────────────────── 작업 실행 ─────────────────────────
    def set_running(self, running):
        for k in ("save", "plan", "check", "login", "open", "watch"):
            self.btns[k].state(["disabled"] if running else ["!disabled"])
        self.btns["stop"].state(["!disabled"] if running else ["disabled"])
        self.btns["close"].state(["!disabled"] if self.browser_open else ["disabled"])

    def start(self, argv, ask=True):
        if self.worker and self.worker.is_alive():
            return
        if not self.auto and not self.save_cfg(quiet=True):
            return
        if ask and argv[0] == "--open":
            if not self.targets:
                messagebox.showinfo("확인", "예약할 날짜가 없습니다. 요일 또는 특정 날짜를 설정하세요.")
                return
            tg = "\n".join(f"  {t.label()}  {', '.join(t.times)}" for t in self.targets)
            mode = "[예약하기] → [예]까지 자동" if self.cfg.get("auto_submit") else "[예약하기] 직전에서 멈춤"
            if not messagebox.askyesno("오픈 대기 시작",
                                       f"오픈: {core.fmt_dt(self.open_dt)}\n\n{tg}\n\n{mode}\n\n시작할까요?"):
                return
        self.close_event.clear()
        self.append("─" * 60, logging.INFO)
        self.worker = threading.Thread(target=self.run_job, args=(argv,), daemon=True)
        self.worker.start()
        self.set_running(True)

    def run_job(self, argv):
        try:
            core.run(argv, confirm_fn=self.ask_from_worker, wait_close_fn=self.wait_close,
                     alert_fn=lambda m: self.q.put(("alert", m, None)))
        except Exception as e:  # noqa: BLE001
            logging.getLogger("gui").exception("실행 오류: %s", e)
        finally:
            self.q.put(("done", None, None))

    def ask_from_worker(self, question):
        ev, box = threading.Event(), {}
        self.q.put(("ask", (question, ev, box), None))
        while not ev.wait(0.2):
            if core.STOP.is_set():
                return False
        return box.get("yes", False)

    def wait_close(self, msg):
        self.browser_open = True
        self.q.put(("state", msg, None))
        while not self.close_event.wait(0.3):
            if core.STOP.is_set():
                break
        self.browser_open = False

    def stop(self):
        core.STOP.set()
        self.close_event.set()
        self.append("중지 요청…", logging.WARNING, "warn")

    def close_browser(self):
        self.close_event.set()

    # ───────────────────────── 화면 갱신 (메인 스레드) ─────────────────────────
    def pump(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "log":
                    tag = "warn" if b >= logging.WARNING else ("ok" if "★" in a or "성공" in a else None)
                    self.append(a, b, tag)
                elif kind == "alert":
                    self.popup(a)
                elif kind == "ask":
                    question, ev, box = a
                    box["yes"] = messagebox.askyesno("확인", question)
                    ev.set()
                elif kind == "state":
                    self.append(f"{a}  → [브라우저 닫기]를 누르면 종료합니다.", logging.INFO, "ok")
                    self.set_running(True)
                elif kind == "done":
                    self.set_running(False)
                    self.refresh_plan()
                    if self.auto:
                        self.append("자동 실행 완료 — 10초 뒤 창을 닫습니다.", logging.INFO)
                        self.root.after(10_000, self.root.destroy)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def append(self, text, level=logging.INFO, tag=None):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text + "\n", (tag,) if tag else ())
        if int(self.logbox.index("end-1c").split(".")[0]) > 3000:
            self.logbox.delete("1.0", "500.0")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def popup(self, msg):
        self.root.bell()
        w = tk.Toplevel(self.root)
        w.title("알림")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        ttk.Label(w, text=msg, wraplength=420, font=("맑은 고딕", 11, "bold"), padding=16).pack()
        ttk.Button(w, text="확인", command=w.destroy).pack(pady=(0, 12))
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + 120
        w.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("종료", "작업이 진행 중입니다. 중지하고 닫을까요?"):
                return
            self.stop()
        self.root.after(300, self.root.destroy)


def main():
    args = sys.argv[1:]
    if args and args != ["--auto"]:
        core.main()           # 명령행 인자는 기존 CLI로
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # 고해상도 화면에서 글자 선명하게
        except Exception:  # noqa: BLE001
            pass
    root = tk.Tk()
    App(root, auto=args == ["--auto"])
    root.mainloop()


if __name__ == "__main__":
    main()
