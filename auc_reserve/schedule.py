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
