from __future__ import annotations

import unittest

from evaluation.significance import mutual_information_permutation_test


class SignificanceTest(unittest.TestCase):
    def test_mutual_information_permutation_test_detects_structured_signal(self) -> None:
        result = mutual_information_permutation_test(
            [float(value) for value in range(1, 11)],
            [float(value) for value in range(1, 11)],
            requested_bins=4,
            permutations=200,
            seed=7,
        )

        self.assertTrue(result.passed)
        self.assertIsNotNone(result.p_value)
        self.assertLess(result.p_value or 1.0, 0.05)
        self.assertIsNotNone(result.null_mean)
        self.assertGreater(result.statistic, result.null_mean or 0.0)

    def test_mutual_information_permutation_test_rejects_noise(self) -> None:
        result = mutual_information_permutation_test(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            [2.0, 5.0, 1.0, 6.0, 3.0, 4.0],
            requested_bins=4,
            permutations=200,
            seed=3,
        )

        self.assertFalse(result.passed)
        self.assertIsNotNone(result.p_value)
        self.assertGreater(result.p_value or 0.0, 0.05)


if __name__ == "__main__":
    unittest.main()
