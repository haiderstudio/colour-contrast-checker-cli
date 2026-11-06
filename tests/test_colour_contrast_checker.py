#!/usr/bin/env python3
"""Tests for colour_contrast_checker. Standard library unittest only."""

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from colour_contrast_checker import (  # noqa: E402
    check_pair,
    contrast_ratio,
    format_result,
    parse_css,
    parse_hex,
    parse_pairs,
    relative_luminance,
    run,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class TestHexParsing(unittest.TestCase):
    def test_six_digit(self):
        self.assertEqual(parse_hex("#1a2b3c"), (26, 43, 60))

    def test_three_digit_expands(self):
        self.assertEqual(parse_hex("#fff"), (255, 255, 255))
        self.assertEqual(parse_hex("#000"), (0, 0, 0))

    def test_no_hash_ok(self):
        self.assertEqual(parse_hex("ff0000"), (255, 0, 0))

    def test_uppercase_ok(self):
        self.assertEqual(parse_hex("#FF0000"), (255, 0, 0))

    def test_bad_values_raise(self):
        for bad in ("", "#12", "#12345", "#gggggg", "red", "#1234567"):
            with self.assertRaises(ValueError, msg=bad):
                parse_hex(bad)


class TestRatioMath(unittest.TestCase):
    def test_black_on_white_is_21(self):
        self.assertAlmostEqual(
            contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)

    def test_same_colour_is_1(self):
        self.assertAlmostEqual(
            contrast_ratio((255, 0, 0), (255, 0, 0)), 1.0, places=2)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(
            contrast_ratio((0, 0, 0), (255, 255, 255)),
            contrast_ratio((255, 255, 255), (0, 0, 0)), places=6)

    def test_white_luminance_is_1_black_is_0(self):
        self.assertAlmostEqual(relative_luminance((255, 255, 255)), 1.0)
        self.assertAlmostEqual(relative_luminance((0, 0, 0)), 0.0)

    def test_grey_767676_passes_aa_fails_aaa(self):
        # #767676 on white is 4.54:1 — just over the AA 4.5 line,
        # well under the AAA 7.0 line.
        ratio, aa, aaa, _ = check_pair(
            parse_hex("#767676"), parse_hex("#ffffff"))
        self.assertGreaterEqual(ratio, 4.5)
        self.assertLess(ratio, 7.0)
        self.assertTrue(aa)
        self.assertFalse(aaa)

    def test_grey_777777_fails_aa(self):
        # #777777 on white is 4.48:1 — just under the AA 4.5 line.
        ratio, aa, _, _ = check_pair(
            parse_hex("#777777"), parse_hex("#ffffff"))
        self.assertLess(ratio, 4.5)
        self.assertFalse(aa)

    def test_large_text_thresholds(self):
        # 4.48:1 fails AA normal (4.5) but passes AA large (3.0).
        _, aa_normal, _, _ = check_pair(
            parse_hex("#777777"), parse_hex("#ffffff"), large=False)
        _, aa_large, _, _ = check_pair(
            parse_hex("#777777"), parse_hex("#ffffff"), large=True)
        self.assertFalse(aa_normal)
        self.assertTrue(aa_large)

    def test_level_aaa_uses_aaa_threshold(self):
        _, _, _, aa_level = check_pair(
            parse_hex("#767676"), parse_hex("#ffffff"), level="aa")
        _, _, _, aaa_level = check_pair(
            parse_hex("#767676"), parse_hex("#ffffff"), level="aaa")
        self.assertTrue(aa_level)
        self.assertFalse(aaa_level)


class TestCssParsing(unittest.TestCase):
    def test_rule_with_both_colours(self):
        pairs, skipped = parse_css(
            "body { color: #111111; background-color: #ffffff; }")
        self.assertEqual(pairs, [("body", "#111111", "#ffffff")])
        self.assertEqual(skipped, [])

    def test_rule_without_background_is_skipped(self):
        pairs, skipped = parse_css("h1 { color: #111111; }")
        self.assertEqual(pairs, [])
        self.assertEqual(len(skipped), 1)
        self.assertIn("no background", skipped[0][1])

    def test_non_hex_colour_is_skipped(self):
        pairs, skipped = parse_css(
            "p { color: red; background-color: #ffffff; }")
        self.assertEqual(pairs, [])
        self.assertIn("not hex", skipped[0][1])

    def test_background_shorthand_hex_is_used(self):
        pairs, _ = parse_css("a { color: #000000; background: #ffffff; }")
        self.assertEqual(pairs, [("a", "#000000", "#ffffff")])

    def test_comments_are_ignored(self):
        pairs, _ = parse_css(
            "/* color: #000000; background-color: #ffffff; */\n"
            "body { color: #111111; background-color: #ffffff; }")
        self.assertEqual(len(pairs), 1)

    def test_three_digit_hex_in_css(self):
        pairs, _ = parse_css("body { color: #000; background-color: #fff; }")
        self.assertEqual(pairs, [("body", "#000", "#fff")])


class TestPairsFile(unittest.TestCase):
    def test_plain_pairs(self):
        pairs = parse_pairs("#000000 #ffffff\n#767676 #ffffff body text\n")
        self.assertEqual(pairs[0], ("pair 1", "#000000", "#ffffff"))
        self.assertEqual(pairs[1], ("body text", "#767676", "#ffffff"))

    def test_comments_and_blanks_ignored(self):
        pairs = parse_pairs("# note\n\n#000000 #ffffff\n")
        self.assertEqual(len(pairs), 1)

    def test_bad_line_raises(self):
        with self.assertRaises(ValueError):
            parse_pairs("#000000\n")
        with self.assertRaises(ValueError):
            parse_pairs("red #ffffff\n")


class TestRunAndCli(unittest.TestCase):
    def test_run_passes_and_fails(self):
        self.assertEqual(
            run([("ok", "#000000", "#ffffff")]), 0)
        self.assertEqual(
            run([("bad", "#777777", "#ffffff")]), 1)

    def test_format_line_shows_ratio_and_verdicts(self):
        line = format_result("body", "#111111", "#ffffff",
                             16.10, True, True)
        self.assertIn("16.10:1", line)
        self.assertIn("AA PASS", line)
        self.assertIn("AAA PASS", line)

    def _cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "src" / "colour_contrast_checker.py"),
             *args],
            capture_output=True, text=True, cwd=cwd)

    def test_cli_two_hex_colours(self):
        result = self._cli("#000000", "#ffffff")
        self.assertEqual(result.returncode, 0)
        self.assertIn("21.00:1", result.stdout)

    def test_cli_failing_pair_exits_1(self):
        result = self._cli("#777777", "#ffffff")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)

    def test_cli_level_aaa_fails_aa_only_pair(self):
        result = self._cli("#767676", "#ffffff", "--level", "aaa")
        self.assertEqual(result.returncode, 1)

    def test_cli_css_file(self):
        result = self._cli(str(ROOT / "examples" / "sample.css"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("body", result.stdout)
        self.assertIn("checked", result.stdout)

    def test_cli_pairs_file(self):
        result = self._cli("--pairs", str(ROOT / "examples" / "pairs.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("checked", result.stdout)

    def test_cli_missing_file_exits_2(self):
        result = self._cli("no-such-file.css")
        self.assertEqual(result.returncode, 2)

    def test_cli_bad_hex_exits_2(self):
        result = self._cli("red", "#ffffff")
        self.assertEqual(result.returncode, 2)

    def test_cli_no_args_exits_2(self):
        result = self._cli()
        self.assertEqual(result.returncode, 2)

    def test_cli_runs_from_any_folder(self):
        # The README install is "clone and run in place": the tool
        # must not depend on the folder it is run from or on any
        # other file in the repo. Run it from the examples folder
        # (not the repo root) against the sample CSS and it must
        # still report the same ratios.
        result = subprocess.run(
            [sys.executable, str(ROOT / "src" / "colour_contrast_checker.py"),
             str(ROOT / "examples" / "sample.css")],
            capture_output=True, text=True, cwd=str(ROOT / "examples"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("18.88:1", result.stdout)
        self.assertIn("4.54:1", result.stdout)
        self.assertIn("4.48:1", result.stdout)

    def test_stdlib_only(self):
        # Day 11 lesson: a test importing a third-party module breaks
        # CI on a clean runner. Both files must import stdlib only.
        stdlib = set(sys.stdlib_module_names)
        # The tool itself is a local module, not a third-party import.
        allowed = stdlib | {"colour_contrast_checker"}
        for path in (ROOT / "src" / "colour_contrast_checker.py",
                     Path(__file__).resolve()):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("import "):
                    name = line.split()[1].split(".")[0].rstrip(",")
                    self.assertIn(name, allowed, "%s in %s" % (name, path))
                elif line.startswith("from "):
                    name = line.split()[1].split(".")[0]
                    self.assertIn(name, allowed, "%s in %s" % (name, path))


if __name__ == "__main__":
    unittest.main()
