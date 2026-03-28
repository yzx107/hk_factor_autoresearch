from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class ScoreboardTest(unittest.TestCase):
    def test_scoreboard_payload_shape(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = {
                "scoreboard_id": "score_x",
                "factor_count": 2,
                "comparison_count": 1,
                "missing_comparisons": [],
            }
            path = tmp / "scoreboard_summary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["factor_count"], 2)
            self.assertEqual(loaded["comparison_count"], 1)


if __name__ == "__main__":
    unittest.main()
