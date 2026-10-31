import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import choose_courts  # noqa: E402

ALL = list(range(1, 13))


def free_except(*taken):
    return [c for c in ALL if c not in taken]


class AutoMode(unittest.TestCase):
    def test_first_consecutive_pair(self):
        self.assertEqual(choose_courts(free_except(5), 2), [1, 2])
        self.assertEqual(choose_courts(free_except(1, 3, 5), 2), [6, 7])

    def test_no_pair_picks_closest(self):
        self.assertEqual(choose_courts([1, 4, 8, 12], 2), [1, 4])

    def test_single(self):
        self.assertEqual(choose_courts(free_except(1, 2), 1), [3])


class PreferredMode(unittest.TestCase):
    def test_all_preferred_free(self):
        self.assertEqual(choose_courts(free_except(5), 2, [6, 7]), [6, 7])

    def test_one_taken_fill_adjacent(self):
        # 6번 예약됨 → 7번 유지 + 7번에 붙은 8번
        self.assertEqual(choose_courts(free_except(6), 2, [6, 7]), [7, 8])
        # 7번 예약됨 → 6번 유지 + 6번에 붙은 5번
        self.assertEqual(choose_courts(free_except(7), 2, [6, 7]), [5, 6])

    def test_both_taken_nearest_pair(self):
        self.assertEqual(choose_courts(free_except(6, 7), 2, [6, 7]), [4, 5])
        self.assertEqual(choose_courts(free_except(4, 5, 6, 7), 2, [6, 7]), [8, 9])

    def test_single_preferred_taken(self):
        self.assertEqual(choose_courts(free_except(6), 1, [6]), [5])

    def test_no_fallback(self):
        self.assertEqual(choose_courts(free_except(6), 2, [6, 7], fallback=False), [7])

    def test_too_few_free(self):
        self.assertEqual(choose_courts([3], 2, [6, 7]), [3])
        self.assertEqual(choose_courts([], 2), [])


if __name__ == "__main__":
    unittest.main()
