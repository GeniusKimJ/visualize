import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import slot_starts_at  # noqa: E402


class SlotStartsAt(unittest.TestCase):
    def test_range_matches_start_only(self):
        self.assertTrue(slot_starts_at("19:00~20:00 A코트 신청", "19:00"))
        self.assertFalse(slot_starts_at("19:00~20:00 A코트 신청", "20:00"))

    def test_zero_padding(self):
        self.assertTrue(slot_starts_at("09:00 - 10:00 B코트", "9:00"))
        self.assertTrue(slot_starts_at("9:00~10:00", "09:00"))

    def test_single_time(self):
        self.assertTrue(slot_starts_at("20:00 A코트", "20:00"))
        self.assertFalse(slot_starts_at("A코트 마감", "20:00"))


if __name__ == "__main__":
    unittest.main()
