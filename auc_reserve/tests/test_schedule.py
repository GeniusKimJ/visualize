import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schedule import KST, build_targets, calendar_url, target_week, upcoming_open  # noqa: E402


def kst(*a):
    return datetime(*a, tzinfo=KST)


CFG = {
    "target_days": [
        {"weekday": "TUE", "times": ["19:00"], "facilities": ["A코트"]},
        {"weekday": "THU", "times": ["20:00"], "facilities": ["B코트"]},
    ],
    "default_times": ["18:00"],
    "default_facilities": ["C코트"],
}


class UpcomingOpen(unittest.TestCase):
    def test_saturday_gives_next_day(self):
        self.assertEqual(upcoming_open(kst(2026, 10, 31, 15, 0)), kst(2026, 11, 1, 10, 0))

    def test_sunday_before_open(self):
        self.assertEqual(upcoming_open(kst(2026, 11, 1, 9, 20)), kst(2026, 11, 1, 10, 0))

    def test_sunday_shortly_after_open_is_same_day(self):
        self.assertEqual(upcoming_open(kst(2026, 11, 1, 10, 5)), kst(2026, 11, 1, 10, 0))

    def test_sunday_evening_rolls_to_next_week(self):
        self.assertEqual(upcoming_open(kst(2026, 11, 1, 20, 0)), kst(2026, 11, 8, 10, 0))

    def test_custom_time(self):
        self.assertEqual(upcoming_open(kst(2026, 11, 2, 0, 0), "SUN", "09:00"),
                         kst(2026, 11, 8, 9, 0))


class TargetWeek(unittest.TestCase):
    def test_examples(self):
        w = target_week(kst(2026, 11, 1, 10))
        self.assertEqual((w[0], w[-1]), (date(2026, 11, 2), date(2026, 11, 8)))
        w = target_week(kst(2026, 11, 8, 10))
        self.assertEqual((w[0], w[-1]), (date(2026, 11, 9), date(2026, 11, 15)))

    def test_month_boundary(self):
        w = target_week(kst(2026, 11, 29, 10))
        self.assertEqual((w[0], w[-1]), (date(2026, 11, 30), date(2026, 12, 6)))

    def test_year_boundary(self):
        w = target_week(kst(2026, 12, 27, 10))
        self.assertEqual((w[0], w[-1]), (date(2026, 12, 28), date(2027, 1, 3)))


class BuildTargets(unittest.TestCase):
    def test_order_and_dates(self):
        t = build_targets(CFG, kst(2026, 11, 8, 10))
        self.assertEqual([x.day for x in t], [date(2026, 11, 10), date(2026, 11, 12)])
        self.assertEqual(t[0].times, ["19:00"])
        self.assertEqual(t[1].facilities, ["B코트"])

    def test_skip_and_extra(self):
        cfg = dict(CFG, skip_dates=["2026-11-10"],
                   extra_dates=["2026-11-14", {"date": "2026-11-15", "times": ["07:00"]}])
        t = build_targets(cfg, kst(2026, 11, 8, 10))
        self.assertEqual([x.day for x in t],
                         [date(2026, 11, 12), date(2026, 11, 14), date(2026, 11, 15)])
        self.assertEqual(t[1].times, ["18:00"])
        self.assertEqual(t[2].times, ["07:00"])
        self.assertEqual(t[2].facilities, ["C코트"])

    def test_duplicate_extra_ignored(self):
        cfg = dict(CFG, extra_dates=["2026-11-10"])
        self.assertEqual(len(build_targets(cfg, kst(2026, 11, 8, 10))), 2)

    def test_month_boundary_targets(self):
        t = build_targets(CFG, kst(2026, 11, 29, 10))
        self.assertEqual([x.day for x in t], [date(2026, 12, 1), date(2026, 12, 3)])

    def test_label(self):
        t = build_targets(CFG, kst(2026, 11, 8, 10))
        self.assertEqual(t[0].label(), "11/10(화)")


class CalendarUrl(unittest.TestCase):
    def test_month_param(self):
        self.assertIn("yearMonthDay=2026-12-01", calendar_url(date(2026, 12, 3)))
        self.assertIn("yearMonthDay=2026-12-03", calendar_url(date(2026, 12, 3), False))


if __name__ == "__main__":
    unittest.main()
