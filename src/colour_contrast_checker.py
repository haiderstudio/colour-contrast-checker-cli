#!/usr/bin/env python3
"""Check colour contrast against WCAG AA and AAA.

Run: python3 src/colour_contrast_checker.py <css-file>
     python3 src/colour_contrast_checker.py --pairs pairs.txt
     python3 src/colour_contrast_checker.py "#111111" "#ffffff"

The tool reads hex colour pairs — from a CSS file (each rule's `color`
against its `background-color`), from a pairs file, or from two hex
colours on the command line — and reports the WCAG contrast ratio and
an AA / AAA pass or fail for each pair. It exits 0 when every pair
passes the chosen level and 1 when any pair fails, so it can fail CI.

It is report-only: it never changes a CSS file. It only understands
hex colours (#rgb and #rrggbb). Any other colour form (named colours,
rgb(), var()) is skipped and reported as skipped, never guessed.

Python standard library only.
"""

import argparse
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

# WCAG 2.1 thresholds: (normal text, large text).
THRESHOLDS = {
    "aa": (4.5, 3.0),
    "aaa": (7.0, 4.5),
}

HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+);?")


def parse_hex(value):
    """Parse a hex colour string into an (r, g, b) tuple of 0-255 ints.

    Accepts '#rgb' and '#rrggbb' (case-insensitive, with or without
    the leading '#'). Raises ValueError for anything else.
    """
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3 and all(c in "0123456789abcdefABCDEF" for c in text):
        text = "".join(c * 2 for c in text)
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError("not a hex colour: %s" % value)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _linear(channel):
    """Convert one sRGB channel (0-255) to linear light (0-1)."""
    c = channel / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    """WCAG relative luminance of an (r, g, b) colour, 0-1."""
    r, g, b = rgb
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(fg, bg):
    """WCAG contrast ratio between two (r, g, b) colours, 1.0-21.0."""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def check_pair(fg, bg, level="aa", large=False):
    """Check one pair. Returns (ratio, aa_pass, aaa_pass, level_pass).

    level is the level the caller cares about ("aa" or "aaa");
    level_pass is whether the pair meets that level's threshold.
    """
    ratio = contrast_ratio(fg, bg)
    aa_limit, aaa_limit = THRESHOLDS["aa"], THRESHOLDS["aaa"]
    if large:
        aa_pass = ratio >= aa_limit[1]
        aaa_pass = ratio >= aaa_limit[1]
    else:
        aa_pass = ratio >= aa_limit[0]
        aaa_pass = ratio >= aaa_limit[0]
    level_pass = aaa_pass if level == "aaa" else aa_pass
    return ratio, aa_pass, aaa_pass, level_pass


def parse_css(text):
    """Pull (label, fg, bg) pairs out of CSS text.

    Each rule that has both a `color` and a `background-color` (or a
    `background` shorthand holding a hex colour) gives one pair, labelled
    with the rule's selector. Rules with a colour but no background are
    reported as skipped — the background is not guessed. Rules whose
    colours are not hex are skipped too.

    Returns (pairs, skipped) where pairs is a list of
    (label, fg_hex, bg_hex) and skipped is a list of (label, reason).
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    pairs = []
    skipped = []
    for match in RULE_RE.finditer(text):
        selector = " ".join(match.group(1).split())
        body = match.group(2)
        decls = {}
        for name, value in DECL_RE.findall(body):
            decls[name.strip().lower()] = value.strip()
        fg_text = decls.get("color")
        bg_text = decls.get("background-color")
        if bg_text is None and "background" in decls:
            found = HEX_RE.search(decls["background"])
            bg_text = found.group(0) if found else None
        if fg_text is None:
            continue
        if bg_text is None:
            skipped.append((selector, "colour set, no background"))
            continue
        fg_match = HEX_RE.search(fg_text)
        bg_match = HEX_RE.search(bg_text)
        if fg_match is None or bg_match is None:
            skipped.append((selector, "colour is not hex"))
            continue
        pairs.append((selector, fg_match.group(0), bg_match.group(0)))
    return pairs, skipped


def parse_pairs(text):
    """Pull (label, fg, bg) pairs out of a pairs file.

    One pair per line: `foreground background` or
    `foreground background label`. Lines starting with `# ` and blank
    lines are ignored. (A line starting with a hex colour, such as
    `#000000`, is a pair, not a comment.) A line with fewer than two
    fields, or with a field that is not a hex colour, raises
    ValueError.
    """
    pairs = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("# "):
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ValueError("line %d: need two colours: %s" % (lineno, raw))
        try:
            parse_hex(fields[0])
            parse_hex(fields[1])
        except ValueError:
            raise ValueError("line %d: not hex colours: %s" % (lineno, raw))
        label = " ".join(fields[2:]) if len(fields) > 2 else "pair %d" % lineno
        pairs.append((label, fields[0], fields[1]))
    return pairs


def format_result(label, fg_hex, bg_hex, ratio, aa_pass, aaa_pass):
    """One result line, e.g. 'PASS  body  #111111 on #ffffff  16.10:1  AA PASS  AAA PASS'."""
    verdict = "PASS" if aa_pass else "FAIL"
    return "%-4s  %-28s  %s on %-7s  %5.2f:1  AA %-4s  AAA %-4s" % (
        verdict, label, fg_hex, bg_hex, ratio,
        "PASS" if aa_pass else "FAIL",
        "PASS" if aaa_pass else "FAIL")


def run(pairs, level="aa", large=False):
    """Check a list of (label, fg_hex, bg_hex) pairs.

    Prints one line per pair plus a summary to standard output.
    Returns 0 when every pair passes the chosen level, 1 otherwise.
    """
    failed = 0
    for label, fg_hex, bg_hex in pairs:
        fg = parse_hex(fg_hex)
        bg = parse_hex(bg_hex)
        ratio, aa_pass, aaa_pass, level_pass = check_pair(
            fg, bg, level=level, large=large)
        print(format_result(label, fg_hex, bg_hex, ratio, aa_pass, aaa_pass))
        if not level_pass:
            failed += 1
    total = len(pairs)
    print("%d checked, %d passed %s, %d failed %s"
          % (total, total - failed, level.upper(), failed, level.upper()))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="colour_contrast_checker",
        description="Check colour contrast against WCAG AA and AAA.")
    parser.add_argument("input", nargs="?",
                        help="CSS file, or foreground hex colour")
    parser.add_argument("background", nargs="?",
                        help="background hex colour (with a foreground colour)")
    parser.add_argument("--pairs", default=None, metavar="FILE",
                        help="file of 'foreground background [label]' pairs")
    parser.add_argument("--level", choices=("aa", "aaa"), default="aa",
                        help="level to fail on (default: aa)")
    parser.add_argument("--large", action="store_true",
                        help="use large-text thresholds (AA 3:1, AAA 4.5:1)")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)

    pairs = []
    skipped = []

    if args.pairs is not None:
        try:
            text = Path(args.pairs).read_text(encoding="utf-8")
        except OSError as exc:
            print("error: cannot read pairs file: %s" % exc, file=sys.stderr)
            return 2
        try:
            pairs = parse_pairs(text)
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
    elif args.input is not None and args.background is not None:
        try:
            parse_hex(args.input)
            parse_hex(args.background)
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        pairs = [("command line", args.input, args.background)]
    elif args.input is not None:
        path = Path(args.input)
        if not path.is_file():
            print("error: no such file: %s" % args.input, file=sys.stderr)
            return 2
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print("error: cannot read file: %s" % exc, file=sys.stderr)
            return 2
        pairs, skipped = parse_css(text)
    else:
        parser.print_usage(sys.stderr)
        print("error: give a CSS file, --pairs FILE, or two hex colours",
              file=sys.stderr)
        return 2

    if not pairs and not skipped:
        print("error: no colour pairs found", file=sys.stderr)
        return 1
    if not pairs:
        print("error: no colour pairs found (%d skipped)"
              % len(skipped), file=sys.stderr)
        for label, reason in skipped:
            print("skipped %s (%s)" % (label, reason), file=sys.stderr)
        return 1

    code = run(pairs, level=args.level, large=args.large)
    for label, reason in skipped:
        print("skipped %s (%s)" % (label, reason), file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
