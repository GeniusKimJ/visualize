import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import parse_calendar, pick_slot  # noqa: E402

# 실제 달력 구조를 줄인 것 (2026-10-31 기준: 06일은 열림, 07일은 아직 비어 있음)
HTML = """<a class="header__links__1__login">로그인</a>
<div class="calendar_table"><table><tbody><tr>
<td><div><span class="day">06</span></div>
<ul class="yy-list">
<li class="impossible"><a href="javascript:void(0);"><strong>불</strong>18:50</a></li>
<li class="possible"><a class="possible" onclick="fn_facilityResSelect('1','','2026-11-06','2030','2200'); return false;"><strong>가</strong>20:30</a></li>
<td><div><span class="day">07</span></div>
<ul class="yy-list">
</tr></tbody></table></div>"""


class ParseCalendar(unittest.TestCase):
    def test_open_day(self):
        st = parse_calendar(HTML, date(2026, 11, 6))
        self.assertTrue(st["opened"])
        self.assertTrue(st["logged_out"])
        self.assertEqual(list(st["slots"]), ["2030"])

    def test_not_open_day(self):
        st = parse_calendar(HTML, date(2026, 11, 7))
        self.assertFalse(st["opened"])
        self.assertEqual(st["slots"], {})

    def test_missing_day(self):
        self.assertFalse(parse_calendar(HTML, date(2026, 11, 8))["opened"])

    def test_pick_priority(self):
        slots = parse_calendar(HTML, date(2026, 11, 6))["slots"]
        self.assertEqual(pick_slot(slots, ["18:50", "20:30"])[0], "20:30")
        self.assertIn("'2030','2200'", pick_slot(slots, ["20:30"])[1])
        self.assertIsNone(pick_slot(slots, ["18:50"]))


if __name__ == "__main__":
    unittest.main()
