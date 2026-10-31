"""예약 오픈 일시와 목표 날짜 계산 (표준 라이브러리만 사용)."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")

WEEKDAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
WEEKDAY_KO = "월화수목금토일"

CALENDAR_URL = (
    "https://www.auc.or.kr/reservation/program/facility/calendar1"
    "?yearMonthDay={ymd}&menuLevel=2&menuNo=419&facilityCategoryNo=1"
)


@dataclass
class Target:
    day: date
    times: list = field(default_factory=list)
    facilities: list = field(default_factory=list)
    source: str = ""

    def label(self):
        return f"{self.day.month}/{self.day.day}({WEEKDAY_KO[self.day.weekday()]})"


def parse_hms(s):
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])


def parse_date(s):
    return date.fromisoformat(s)


def upcoming_open(now, open_weekday="SUN", open_time="10:00:00", grace_hours=6):
    """now 기준으로 다가오는(또는 방금 지난 grace_hours 이내의) 오픈 일시."""
    wd = WEEKDAYS[open_weekday.upper()]
    days_ahead = (wd - now.weekday()) % 7
    cand = datetime.combine(now.date() + timedelta(days=days_ahead),
                            parse_hms(open_time), tzinfo=now.tzinfo)
    if cand + timedelta(hours=grace_hours) < now:
        cand += timedelta(days=7)
    return cand


def target_week(open_dt):
    """오픈일 다음에 오는 월요일부터 일요일까지 7일."""
    d = open_dt.date() if isinstance(open_dt, datetime) else open_dt
    offset = (0 - d.weekday()) % 7 or 7
    start = d + timedelta(days=offset)
    return [start + timedelta(days=i) for i in range(7)]


def build_targets(cfg, open_dt):
    """target_days 요일 + extra_dates - skip_dates, 우선순위 순서 유지."""
    week = target_week(open_dt)
    skip = {parse_date(s) for s in cfg.get("skip_dates", [])}
    default_times = cfg.get("default_times", [])
    default_fac = cfg.get("default_facilities", [])
    out, seen = [], set()

    def add(t):
        if t.day in skip or t.day in seen:
            return
        seen.add(t.day)
        out.append(t)

    for td in cfg.get("target_days", []):
        wd = WEEKDAYS[td["weekday"].upper()]
        d = next(x for x in week if x.weekday() == wd)
        add(Target(d, list(td.get("times", default_times)),
                   list(td.get("facilities", default_fac)),
                   f"target_days:{td['weekday'].upper()}"))

    for ex in cfg.get("extra_dates", []):
        if isinstance(ex, str):
            add(Target(parse_date(ex), list(default_times), list(default_fac), "extra_dates"))
        else:
            add(Target(parse_date(ex["date"]), list(ex.get("times", default_times)),
                       list(ex.get("facilities", default_fac)), "extra_dates"))
    return out


def calendar_url(d, first_of_month=True):
    ymd = d.replace(day=1) if first_of_month else d
    return CALENDAR_URL.format(ymd=ymd.isoformat())


# ── 이용일 N일 전 오픈 방식 (예: 7일 전 15:00) ─────────────────────
def _candidates(cfg, today, horizon):
    """target_days 요일(앞으로 horizon일) + extra_dates - skip_dates. 우선순위 순서, 날짜 중복 제거."""
    skip = {parse_date(s) for s in cfg.get("skip_dates", [])}
    default_times = cfg.get("default_times", [])
    default_fac = cfg.get("default_facilities", [])
    out, seen = [], set()

    def add(t):
        if t.day in skip or t.day in seen or t.day <= today:
            return
        seen.add(t.day)
        out.append(t)

    for ex in cfg.get("extra_dates", []):
        if isinstance(ex, str):
            add(Target(parse_date(ex), list(default_times), list(default_fac), "extra_dates"))
        else:
            add(Target(parse_date(ex["date"]), list(ex.get("times", default_times)),
                       list(ex.get("facilities", default_fac)), "extra_dates"))
    for td in cfg.get("target_days", []):
        wd = WEEKDAYS[td["weekday"].upper()]
        for k in range(1, horizon + 1):
            d = today + timedelta(days=k)
            if d.weekday() == wd:
                add(Target(d, list(td.get("times", default_times)),
                           list(td.get("facilities", default_fac)),
                           f"target_days:{td['weekday'].upper()}"))
    return out


def rolling_open_of(day, cfg):
    n = int(cfg.get("open_days_before", 7))
    return datetime.combine(day - timedelta(days=n), parse_hms(cfg.get("open_time", "15:00:00")),
                            tzinfo=KST)


def rolling_plan(cfg, now, grace_hours=6):
    """가장 가까운 오픈 시점과 그때 열리는 목표 날짜. 없으면 (None, [])."""
    n = int(cfg.get("open_days_before", 7))
    cands = _candidates(cfg, now.date(), n + 21)
    upcoming = [(rolling_open_of(t.day, cfg), t) for t in cands]
    upcoming = [(o, t) for o, t in upcoming if o + timedelta(hours=grace_hours) >= now]
    if not upcoming:
        return None, []
    first = min(o for o, _ in upcoming)
    return first, [t for o, t in upcoming if o == first]


def rolling_bookable(cfg, now):
    """이미 열려 있고 아직 이용일이 지나지 않은 목표 날짜 (빈자리 감시용)."""
    n = int(cfg.get("open_days_before", 7))
    return [t for t in _candidates(cfg, now.date(), n + 1) if rolling_open_of(t.day, cfg) <= now]
