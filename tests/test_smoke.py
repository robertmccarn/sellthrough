from __future__ import annotations

import unittest

from sellthrough.smoke import SmokeCheck, format_smoke_checks


class SmokeFormattingTests(unittest.TestCase):
    def test_format_smoke_checks_renders_one_line_per_check(self) -> None:
        output = format_smoke_checks(
            [
                SmokeCheck("config", "PASS", "environment=production"),
                SmokeCheck("marketplace insights", "WARN", "access pending"),
            ]
        )

        self.assertEqual(
            output,
            "\n".join(
                [
                    "[PASS] config: environment=production",
                    "[WARN] marketplace insights: access pending",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
